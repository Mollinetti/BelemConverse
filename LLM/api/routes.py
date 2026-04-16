"""
API routes for BelemConverse.
"""

import re
import time
import logging
from typing import List
from pathlib import Path
import sys

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from .schemas import (
    ChatRequest, ChatResponse, Place, PlaceResult,
    HealthResponse, LanguagesResponse, ErrorResponse, IngestionResponse
)
from .dependencies import get_rag_agent, is_system_ready, get_system_status
from . import __version__
from data.csv_ingestion import CSVIngestionPipeline
from core.query_planner import QueryPlanner
from core.unified_retriever import UnifiedRetriever
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine
from datetime import datetime
import json

logger = logging.getLogger(__name__)

router = APIRouter()


def extract_places_from_response(response: str, documents: list) -> List[Place]:
    """
    Extract place information from LLM response and retrieved documents.
    
    Args:
        response: LLM response text
        documents: Retrieved documents with place metadata
        
    Returns:
        List of Place objects
    """
    places = []
    seen_names = set()
    
    for doc in documents:
        metadata = doc.metadata if hasattr(doc, 'metadata') else {}
        
        # Extract name from metadata or content
        name = metadata.get('title', '')
        if not name:
            # Try to extract from page_content
            content = doc.page_content if hasattr(doc, 'page_content') else ''
            for line in content.split('\n'):
                if line.lower().startswith('title:'):
                    name = line.split(':', 1)[1].strip()
                    break
        
        if not name or name.lower() in seen_names:
            continue
        
        seen_names.add(name.lower())
        
        # Extract coordinates
        lat = metadata.get('location/lat')
        lng = metadata.get('location/lng')
        
        try:
            lat = float(lat) if lat else None
            lng = float(lng) if lng else None
        except (ValueError, TypeError):
            lat, lng = None, None
        
        # Extract other fields
        try:
            rating = float(metadata.get('totalScore', 0)) or None
        except (ValueError, TypeError):
            rating = None
        
        try:
            reviews = int(metadata.get('reviewsCount', 0)) or None
        except (ValueError, TypeError):
            reviews = None
        
        try:
            distance = float(metadata.get('distance_km', 0)) or None
        except (ValueError, TypeError):
            distance = None
        
        place = Place(
            name=name,
            address=metadata.get('address', metadata.get('addressFormatted', '')),
            category=metadata.get('categoryName', ''),
            rating=rating,
            reviews_count=reviews,
            lat=lat,
            lng=lng,
            phone=metadata.get('phone', ''),
            distance_km=distance,
            source=metadata.get('data_source', 'database')
        )
        places.append(place)
    
    return places[:5]  # Limit to top 5 places


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the API and its components.
    """
    status = get_system_status()
    
    return HealthResponse(
        status="healthy" if is_system_ready() else "initializing",
        version=__version__,
        llm_loaded=status.get("llm_loaded", False),
        vector_store_loaded=status.get("vector_store_loaded", False)
    )


@router.get("/languages", response_model=LanguagesResponse)
async def get_languages():
    """
    Get available languages.
    
    Returns the list of supported languages for the chatbot.
    """
    return LanguagesResponse()


@router.get("/places/{placeId}", response_model=Place)
async def get_place(placeId: str):
    """
    Get place by placeId per OpenAPI spec.
    """
    try:
        # Load places index from canonical_places.jsonl
        places_file = Path(__file__).parent.parent / "data" / "canonical_places.jsonl"
        
        if not places_file.exists():
            raise HTTPException(status_code=404, detail="Places index not found. Please run ingestion first.")
        
        # Search for place
        with open(places_file, 'r', encoding='utf-8') as f:
            for line in f:
                place = json.loads(line)
                if place.get('placeId') == placeId:
                    # Convert location dict to LatLng if present
                    if place.get('location') and isinstance(place['location'], dict):
                        loc = place['location']
                        if loc.get('lat') is not None and loc.get('lng') is not None:
                            from .schemas import LatLng
                            place['location'] = LatLng(lat=loc['lat'], lng=loc['lng'])
                        else:
                            place['location'] = None
                    return Place(**place)
        
        raise HTTPException(status_code=404, detail=f"Place {placeId} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving place {placeId}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse, responses={
    500: {"model": ErrorResponse, "description": "Internal server error"},
    503: {"model": ErrorResponse, "description": "Service unavailable"},
    400: {"model": ErrorResponse, "description": "Bad request"}
})
async def chat(request: ChatRequest):
    """
    Chat query -> plan -> retrieve -> LLM summarize per OpenAPI spec.
    """
    start_time = time.time()
    
    # Check if system is ready
    if not is_system_ready():
        raise HTTPException(
            status_code=503,
            detail="RAG system is still initializing. Please try again in a moment."
        )
    
    try:
        # Parse nowIso if provided
        now_datetime = None
        if request.nowIso:
            try:
                now_datetime = datetime.fromisoformat(request.nowIso.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Invalid nowIso format: {request.nowIso}")
        
        # Get user location (support both userLocation and legacy coordinates)
        user_location = None
        if request.userLocation:
            user_location = {'lat': request.userLocation.lat, 'lng': request.userLocation.lng}
        elif request.coordinates:
            user_location = {'lat': request.coordinates.lat, 'lng': request.coordinates.lng}
        
        # Convert filters to dict
        filters_dict = None
        if request.filters:
            filters_dict = request.filters.dict(exclude_none=True)
            # Convert placeType to place_type for query planner
            if 'placeType' in filters_dict:
                filters_dict['placeType'] = filters_dict['placeType']
        
        # Create Query Plan with TFIDF intent classifier
        from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
        intent_classifier = SimpleTFIDFIntentClassifier()
        query_planner = QueryPlanner(intent_classifier=intent_classifier)
        query_plan = query_planner.create_query_plan(
            message=request.message,
            user_location=user_location,
            explicit_language=request.language,
            filters=filters_dict
        )
        
        logger.info(f"Query Plan: {json.dumps(query_planner.plan_to_dict(query_plan), indent=2)}")
        
        # Check for tour planning intent and route accordingly
        agent = get_rag_agent()
        
        # Detect tour planning intent using the same method as EnhancedRAGAgent
        intent_result = intent_classifier.predict(request.message)
        is_tour_query = _is_tour_planning_query(intent_result, request.message)
        
        if is_tour_query:
            logger.info("Detected tour planning intent, routing to tour planner")
            
            # Convert user_location to tuple format expected by tour planner
            user_coordinates = None
            if user_location:
                user_coordinates = (user_location['lat'], user_location['lng'])
            
            # Handle tour planning using EnhancedRAGAgent
            try:
                answer = agent._handle_tour_planning(
                    question=request.message,
                    intent_result=intent_result,
                    user_coordinates=user_coordinates
                )
                
                # For tour responses, return empty place results (tours are text-only)
                place_results = []
                
                processing_time = (time.time() - start_time) * 1000
                logger.info(f"Tour response generated in {processing_time:.0f}ms")
                
                return ChatResponse(
                    language=query_plan.language,
                    answer=answer,
                    results=place_results,
                    debug=query_plan.debug,
                    # Legacy fields
                    response=answer,
                    processing_time_ms=round(processing_time, 1)
                )
            except Exception as e:
                logger.error(f"Tour planning failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Fall back to regular query flow
                logger.info("Falling back to regular query flow")
        
        # Regular query flow (non-tour queries)
        # Load places index
        places_file = Path(__file__).parent.parent / "data" / "canonical_places.jsonl"
        if not places_file.exists():
            raise HTTPException(
                status_code=400,
                detail="Places index not found. Please run /ingest/csv first."
            )
        
        places_index = []
        with open(places_file, 'r', encoding='utf-8') as f:
            for line in f:
                places_index.append(json.loads(line))
        
        # Initialize shared modules for UnifiedRetriever
        from core.intent_classifier import SimpleTFIDFIntentClassifier
        intent_classifier = SimpleTFIDFIntentClassifier()
        intent_classifier.train()
        
        place_cache = PlaceCache(places_index)
        category_matcher = CategoryMatcher(intent_classifier)
        ranking_engine = RankingEngine()
        
        # Retrieve using unified retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,  # No vector store in API for now
            osm_client=None  # No OSM client in API for now
        )
        
        # Convert query_plan to dict format expected by UnifiedRetriever
        query_plan_dict = {
            'intent': query_plan.intent,
            'slots': query_plan.slots,
            'retrieval_strategy': 'structured_only',
            'proximity_intent_detected': query_plan.slots.get('proximity_intent_detected', False),
            'language': query_plan.language
        }
        
        retrieval_result = retriever.retrieve(query_plan_dict)
        
        logger.info(f"Retrieved {len(retrieval_result.places)} places using {retrieval_result.strategy_used}")
        
        # Convert places to PlaceResult schema
        place_results = []
        for place in retrieval_result.places:
            try:
                place_dict = place.copy()
                
                # Convert location dict to LatLng if present
                if place_dict.get('location') and isinstance(place_dict['location'], dict):
                    loc = place_dict['location']
                    if loc.get('lat') is not None and loc.get('lng') is not None:
                        from .schemas import LatLng
                        place_dict['location'] = LatLng(lat=loc['lat'], lng=loc['lng'])
                    else:
                        place_dict['location'] = None
                
                place_results.append(PlaceResult(**place_dict))
            except Exception as e:
                logger.error(f"Error converting place to PlaceResult: {e}")
                logger.error(f"Place data: {place_dict.get('placeId', 'NO_PLACE_ID')}")
                import traceback
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=400,
                    detail=f"Error converting place result: {str(e)}"
                )
        
        # Generate LLM response (summarization only)
        # Convert places back to old format for generate_llm_answer
        results_for_llm = []
        for place in retrieval_result.places:
            # Create a simple object with place, distanceKm, and openNowStatus attributes
            class PlaceResultForLLM:
                def __init__(self, place_dict):
                    self.place = place_dict
                    self.distanceKm = place_dict.get('distanceKm')
                    self.openNowStatus = place_dict.get('openNowStatus', 'unknown')
            
            results_for_llm.append(PlaceResultForLLM(place))
        
        answer = generate_llm_answer(
            agent=agent,
            message=request.message,
            results=results_for_llm,
            language=query_plan.language,
            query_plan=query_plan
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(f"Chat response generated in {processing_time:.0f}ms")
        
        return ChatResponse(
            language=query_plan.language,
            answer=answer,
            results=place_results,
            debug=query_plan.debug,
            # Legacy fields
            response=answer,
            processing_time_ms=round(processing_time, 1)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


def _is_tour_planning_query(intent_result: dict, question: str) -> bool:
    """
    Check if the query is asking for tour/itinerary planning.
    
    This is a helper function that mirrors the logic in EnhancedRAGAgent.
    """
    # Check if tour_planning is the PRIMARY intent with good confidence
    primary_intent = intent_result.get('primary_intent', '')
    primary_confidence = intent_result.get('primary_intent_confidence', 0.0)
    
    if primary_intent == 'tour_planning' and primary_confidence >= 0.3:
        return True
    
    # Fallback to keyword detection - require explicit tour keywords
    question_lower = question.lower()
    tour_keywords = [
        'tour', 'itinerary', 'day trip', 'plan my day', 'what to do in a day',
        'roteiro', 'passeio pelo', 'o que fazer em um dia', 'dia em belém',
        'planejar meu dia', 'one day itinerary', 'walking tour', 'food tour',
        'create an itinerary', 'plan a trip'
    ]
    
    return any(keyword in question_lower for keyword in tour_keywords)


def generate_llm_answer(
    agent,
    message: str,
    results: List,
    language: str,
    query_plan
) -> str:
    """
    Generate LLM answer summarizing the retrieved results.
    
    Per LLM contract: Only summarize provided results, no hallucination.
    """
    if not results:
        if language == 'pt-BR':
            return "Não encontrei lugares que correspondam à sua busca. Tente ampliar o raio de busca, escolher um tipo diferente, ou desativar o filtro de 'aberto agora'."
        else:
            return "I couldn't find any places matching your search. Try widening the search radius, choosing a different type, or disabling the 'open now' filter."
    
    # Build context from results
    results_text = []
    for i, result in enumerate(results, 1):
        place = result.place
        name = place.get('title') or place.get('titleFormatted', 'Unknown')
        address = place.get('addressFormatted') or place.get('address', '')
        category = place.get('categoryName', '')
        rating = place.get('totalScore')
        reviews = place.get('reviewsCount')
        distance = result.distanceKm
        open_status = result.openNowStatus
        
        result_desc = f"{i}. {name}"
        if category:
            result_desc += f" ({category})"
        if address:
            result_desc += f" - {address}"
        if distance is not None:
            result_desc += f" - {distance:.2f}km away"
        if rating:
            result_desc += f" - Rating: {rating:.1f}/5"
        if reviews:
            result_desc += f" ({reviews} reviews)"
        if open_status:
            if language == 'pt-BR':
                status_text = {'open': 'aberto', 'closed': 'fechado', 'unknown': 'horário desconhecido'}.get(open_status, open_status)
            else:
                status_text = {'open': 'open', 'closed': 'closed', 'unknown': 'hours unknown'}.get(open_status, open_status)
            result_desc += f" - {status_text}"
        
        results_text.append(result_desc)
    
    context = "\n".join(results_text)
    
    # Generate response using agent (with summarization-only prompt)
    try:
        # Use agent's query method but with explicit instruction to only use provided results
        prompt_message = message
        if language == 'pt-BR':
            system_instruction = "Você é um assistente que recomenda lugares. Use APENAS os lugares fornecidos abaixo. Não invente lugares. Se os resultados estiverem vazios, faça uma pergunta esclarecedora ou sugira ampliar as restrições."
        else:
            system_instruction = "You are an assistant that recommends places. Use ONLY the places provided below. Do not invent places. If results are empty, ask a clarifying question or suggest widening constraints."
        
        # For now, use simple template-based response
        # In production, this would use the LLM with proper prompt
        if language == 'pt-BR':
            answer = f"Aqui estão os lugares encontrados:\n\n{context}\n\nEstes são os lugares que correspondem à sua busca."
        else:
            answer = f"Here are the places found:\n\n{context}\n\nThese are the places matching your search."
        
        return answer
        
    except Exception as e:
        logger.error(f"Error generating LLM answer: {e}")
        # Fallback response
        if language == 'pt-BR':
            return f"Encontrei {len(results)} lugares:\n\n{context}"
        else:
            return f"Found {len(results)} places:\n\n{context}"


@router.post("/ingest/csv", response_model=IngestionResponse)
async def ingest_csv(file: UploadFile = File(...)):
    """
    Ingest Places from CSV and build index.
    
    Accepts a CSV file upload, processes it according to spec/02-csv-mapping.md,
    and outputs canonical_places.jsonl and ingestion_report.json.
    """
    try:
        # Save uploaded file temporarily
        temp_dir = Path(__file__).parent.parent.parent / "data" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / file.filename
        
        with open(temp_file, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Received CSV file: {file.filename}, size: {len(content)} bytes")
        
        # Run ingestion pipeline
        pipeline = CSVIngestionPipeline()
        report = pipeline.ingest_csv(temp_file)
        
        # Clean up temp file
        temp_file.unlink()
        
        return IngestionResponse(
            ingestedCount=report['ingestedCount'],
            skippedCount=report['skippedCount'],
            outputFiles=report['outputFiles']
        )
        
    except Exception as e:
        logger.error(f"CSV ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"CSV ingestion failed: {str(e)}"
        )


@router.post("/clear-history")
async def clear_history():
    """
    Clear the conversation history.
    """
    try:
        agent = get_rag_agent()
        if hasattr(agent, 'clear_conversation_history'):
            agent.clear_conversation_history()
        return {"status": "success", "message": "Conversation history cleared"}
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


