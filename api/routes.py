"""HTTP routes for BelemConverse.

Pipeline per `docs/archive/spec/`:
    Chat request -> Query Plan (TF-IDF intent + slots)
                 -> Deterministic retrieval (open-hours -> proximity -> category -> rank)
                 -> hosted LLM summary of the top 5 results, or a template answer.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from belem_converse import llm
from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
    SimpleTFIDFIntentClassifier,
)
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.query_planner import QueryPlanner
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever

from . import __version__
from .dependencies import BUILD_HINT, get_catalog, get_system_status, is_system_ready
from .schemas import (
    ChatFilters,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    LanguagesResponse,
    LatLng,
    Place,
    PlaceResult,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_RESULTS = 5  # spec: an answer shows at most five places


# ----- module-level singletons (built lazily on first chat) -----------------
_intent_classifier: Optional[SimpleTFIDFIntentClassifier] = None
_query_planner: Optional[QueryPlanner] = None
_place_cache: Optional[PlaceCache] = None
_category_matcher: Optional[CategoryMatcher] = None
_ranking_engine: Optional[RankingEngine] = None
_retriever: Optional[UnifiedRetriever] = None


def _get_intent_classifier() -> SimpleTFIDFIntentClassifier:
    global _intent_classifier
    if _intent_classifier is None:
        clf = SimpleTFIDFIntentClassifier()
        clf.train()
        _intent_classifier = clf
    return _intent_classifier


def _get_query_planner() -> QueryPlanner:
    global _query_planner
    if _query_planner is None:
        _query_planner = QueryPlanner(intent_classifier=_get_intent_classifier())
    return _query_planner


def _load_places_index() -> List[dict]:
    """The catalog loaded at startup; 503 until it exists."""
    catalog = get_catalog()
    if catalog is None:
        raise HTTPException(status_code=503, detail=f"Place catalog not loaded. {BUILD_HINT}")
    return catalog


def _get_retriever() -> UnifiedRetriever:
    """Lazily build the unified retriever over the loaded catalog."""
    global _place_cache, _category_matcher, _ranking_engine, _retriever
    if _retriever is None:
        places_index = _load_places_index()
        _place_cache = PlaceCache(places_index)
        _category_matcher = CategoryMatcher(_get_intent_classifier())
        _ranking_engine = RankingEngine()
        _retriever = UnifiedRetriever(
            place_cache=_place_cache,
            category_matcher=_category_matcher,
            ranking_engine=_ranking_engine,
            vector_store=None,  # FUTURE: wire optional Chroma fallback (ADR-0002)
            osm_client=None,    # FUTURE: wire OSM realtime fallback
        )
    return _retriever


# ----- endpoints ------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    status = get_system_status()
    return HealthResponse(
        status="healthy" if is_system_ready() else "initializing",
        version=__version__,
        llm_loaded=status.get("llm_loaded", False),
        vector_store_loaded=status.get("vector_store_loaded", False),
    )


@router.get("/languages", response_model=LanguagesResponse)
async def get_languages() -> LanguagesResponse:
    return LanguagesResponse()


@router.get("/places/{placeId}", response_model=Place)
async def get_place(placeId: str) -> Place:
    place = next((p for p in _load_places_index() if p.get("placeId") == placeId), None)
    if place is None:
        raise HTTPException(status_code=404, detail=f"Place {placeId} not found")
    place = dict(place)
    loc = place.get("location")
    if isinstance(loc, dict) and loc.get("lat") is not None and loc.get("lng") is not None:
        place["location"] = LatLng(lat=loc["lat"], lng=loc["lng"])
    else:
        place["location"] = None
    return Place(**place)


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Plan -> retrieve -> summarize per OpenAPI spec (`docs/archive/spec/05-openapi.yaml`)."""
    start = time.time()

    if not is_system_ready():
        raise HTTPException(
            status_code=503,
            detail=f"Place catalog not loaded. {BUILD_HINT}",
        )

    # Optional client-supplied "now" timestamp (used by open-hours filtering).
    if request.nowIso:
        try:
            datetime.fromisoformat(request.nowIso.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Invalid nowIso format: %s", request.nowIso)

    user_location: Optional[dict] = None
    if request.userLocation:
        user_location = {"lat": request.userLocation.lat, "lng": request.userLocation.lng}
    elif request.coordinates:
        user_location = {"lat": request.coordinates.lat, "lng": request.coordinates.lng}

    filters_dict = request.filters.dict(exclude_none=True) if request.filters else None

    query_planner = _get_query_planner()

    query_plan = query_planner.create_query_plan(
        message=request.message,
        user_location=user_location,
        explicit_language=request.language,
        filters=filters_dict,
    )
    logger.info("Query Plan: %s", json.dumps(query_planner.plan_to_dict(query_plan), indent=2))

    # ----- Regular query flow ----------------------------------------------
    try:
        retriever = _get_retriever()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Retriever build failed")
        raise HTTPException(status_code=500, detail=f"Retriever error: {exc}") from exc

    query_plan_dict = {
        "intent": query_plan.intent,
        "slots": query_plan.slots,
        "retrieval_strategy": "structured_only",
        "proximity_intent_detected": query_plan.slots.get("proximity_intent_detected", False),
        "language": query_plan.language,
    }
    retrieval_result = retriever.retrieve(query_plan_dict)
    logger.info(
        "Retrieved %d places via %s",
        len(retrieval_result.places),
        retrieval_result.strategy_used,
    )
    top_places = retrieval_result.places[:MAX_RESULTS]

    place_results: List[PlaceResult] = []
    for place in top_places:
        try:
            place_dict = place.copy()
            loc = place_dict.get("location")
            if isinstance(loc, dict) and loc.get("lat") is not None and loc.get("lng") is not None:
                place_dict["location"] = LatLng(lat=loc["lat"], lng=loc["lng"])
            elif isinstance(loc, dict):
                place_dict["location"] = None
            place_results.append(PlaceResult(**place_dict))
        except Exception as exc:
            logger.error(
                "Error converting place %s: %s",
                place.get("placeId", "NO_PLACE_ID"),
                exc,
            )
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=400,
                detail=f"Error converting place result: {exc}",
            ) from exc

    answer, answer_source = await _answer(request.message, top_places, query_plan.language)
    elapsed_ms = (time.time() - start) * 1000
    logger.info("Chat response generated in %.0fms (answer: %s)", elapsed_ms, answer_source)

    return ChatResponse(
        language=query_plan.language,
        answer=answer,
        results=place_results,
        debug={**(query_plan.debug or {}), "answer_source": answer_source},
        response=answer,
        processing_time_ms=round(elapsed_ms, 1),
    )


async def _answer(question: str, places: List[dict], language: str) -> tuple[str, str]:
    """(answer, source): the model's grounded answer, else the template.

    The model is called at most once, and not at all when nothing was found.
    """
    if places:
        text = await llm.summarize(question, places, language)
        if text is not None:
            catalog_titles = [p.get("title") or "" for p in get_catalog() or []]
            if llm.is_grounded(text, places, catalog_titles):
                return llm.strip_markers(text), "llm"
            logger.warning("Model answer named places outside the results; using the template")
    return _generate_answer(places, language), "template"


def _generate_answer(places: List[dict], language: str) -> str:
    """Template answer: used when the model is unconfigured, fails, or strays."""
    if not places:
        if language == "pt-BR":
            return (
                "Não encontrei lugares que correspondam à sua busca. "
                "Tente ampliar o raio de busca, escolher um tipo diferente, "
                "ou desativar o filtro de 'aberto agora'."
            )
        return (
            "I couldn't find any places matching your search. "
            "Try widening the search radius, choosing a different type, "
            "or disabling the 'open now' filter."
        )

    lines: List[str] = []
    for i, place in enumerate(places, 1):
        name = place.get("title") or place.get("titleFormatted") or "Unknown"
        address = place.get("addressFormatted") or place.get("address") or ""
        category = place.get("categoryName") or ""
        rating = place.get("totalScore")
        reviews = place.get("reviewsCount")
        distance = place.get("distanceKm")
        open_status = place.get("openNowStatus")

        parts = [f"{i}. {name}"]
        if category:
            parts.append(f"({category})")
        if address:
            parts.append(f"- {address}")
        if distance is not None:
            parts.append(f"- {distance:.2f}km away")
        if rating:
            parts.append(f"- Rating: {rating:.1f}/5")
        if reviews:
            parts.append(f"({reviews} reviews)")
        if open_status:
            label_map_pt = {"open": "aberto", "closed": "fechado", "unknown": "horário desconhecido"}
            label_map_en = {"open": "open", "closed": "closed", "unknown": "hours unknown"}
            label = (label_map_pt if language == "pt-BR" else label_map_en).get(open_status, open_status)
            parts.append(f"- {label}")
        lines.append(" ".join(parts))

    body = "\n".join(lines)
    if language == "pt-BR":
        return f"Aqui estão os lugares encontrados:\n\n{body}\n\nEstes são os lugares que correspondem à sua busca."
    return f"Here are the places found:\n\n{body}\n\nThese are the places matching your search."

