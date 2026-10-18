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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from belem_converse import follow_ups, llm
from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
    SimpleTFIDFIntentClassifier,
)
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.query_planner import QueryPlanner, merge_slots
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever
from belem_converse.limits import DailyCap, RateLimiter, client_ip, trusted_proxy_hops
from belem_converse.sessions import SessionStore

from . import __version__
from .dependencies import BUILD_HINT, get_catalog, get_system_status, is_system_ready
from .schemas import (
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
MAX_RANKED = 30  # kept per conversation for "see more"
ANNOTATIONS = ("distanceKm", "openNowStatus")  # per-request fields, not in the catalog
SEE_MORE_LINE = {
    "pt-BR": "Mais lugares da sua última busca.",
    "en": "More places from your last search.",
}


sessions = SessionStore()
rate_limiter = RateLimiter()
TRUSTED_PROXY_HOPS = trusted_proxy_hops()
daily_cap = DailyCap()

# ----- module-level singletons (built lazily on first chat) -----------------
_intent_classifier: SimpleTFIDFIntentClassifier | None = None
_query_planner: QueryPlanner | None = None
_place_cache: PlaceCache | None = None
_category_matcher: CategoryMatcher | None = None
_ranking_engine: RankingEngine | None = None
_retriever: UnifiedRetriever | None = None


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


def _load_places_index() -> list[dict]:
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
        429: {"description": "rate_limited: too many messages from this visitor"},
        409: {"description": "conversation_finished: no questions left; "
                            "no_previous_results: nothing to see more of"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse | JSONResponse:
    """Plan -> retrieve -> summarize per OpenAPI spec (`docs/archive/spec/05-openapi.yaml`)."""
    start = time.time()
    started_at = time.monotonic()  # the model's time budget counts from here

    visitor = client_ip(
        http_request.headers.get("x-forwarded-for"),
        http_request.client.host if http_request.client else None,
        TRUSTED_PROXY_HOPS,
    )
    if not rate_limiter.hit(visitor):
        return JSONResponse(status_code=429, content={"code": "rate_limited"})

    if not is_system_ready():
        raise HTTPException(
            status_code=503,
            detail=f"Place catalog not loaded. {BUILD_HINT}",
        )

    session = sessions.get_or_create(str(request.session_id))
    if request.action == "more":
        return _see_more(session, request.language or "pt-BR")
    if session.turns_left <= 0:
        return JSONResponse(
            status_code=409, content={"code": "conversation_finished", "turns_left": 0}
        )
    # Taken before the first await, so parallel requests cannot answer a 5th.
    session.turns_used += 1

    # Optional client-supplied "now" timestamp (used by open-hours filtering).
    if request.nowIso:
        try:
            datetime.fromisoformat(request.nowIso.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Invalid nowIso format: %s", request.nowIso)

    user_location: dict | None = None
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

    # A follow-up refines the conversation's previous question.
    slots = merge_slots(session.last_plan, query_plan.slots)
    session.last_plan = slots
    query_plan_dict = {
        "intent": query_plan.intent,
        "slots": slots,
        "retrieval_strategy": "structured_only",
        "proximity_intent_detected": slots.get("proximity_intent_detected", False),
        "language": query_plan.language,
    }
    # CPU-bound: run it off the event loop so other requests are not stalled.
    retrieval_result = await run_in_threadpool(retriever.retrieve, query_plan_dict)
    logger.info(
        "Retrieved %d places via %s",
        len(retrieval_result.places),
        retrieval_result.strategy_used,
    )
    ranked = retrieval_result.places[:MAX_RANKED]
    top_places = ranked[:MAX_RESULTS]
    place_results = _place_results(top_places)
    session.ranked_ids = [p["placeId"] for p in ranked]
    session.annotations = {
        p["placeId"]: ann
        for p in ranked
        if (ann := {k: p[k] for k in ANNOTATIONS if k in p})
    }
    session.cursor = len(top_places)

    answer, answer_source = await _answer(
        request.message, top_places, query_plan.language, started_at
    )
    elapsed_ms = (time.time() - start) * 1000
    logger.info("Chat response generated in %.0fms (answer: %s)", elapsed_ms, answer_source)

    return ChatResponse(
        language=query_plan.language,
        answer=answer,
        results=place_results,
        turns_left=session.turns_left,
        has_more=session.cursor < len(session.ranked_ids),
        follow_ups=follow_ups.build(slots, query_plan.language, user_location is not None),
        debug={**(query_plan.debug or {}), "answer_source": answer_source},
        processing_time_ms=round(elapsed_ms, 1),
    )


def _see_more(session, language: str) -> ChatResponse | JSONResponse:
    """The next page of the conversation's last ranked list: no search, no model."""
    if not session.ranked_ids:
        return JSONResponse(
            status_code=409,
            content={"code": "no_previous_results", "turns_left": session.turns_left},
        )
    page_ids = session.ranked_ids[session.cursor : session.cursor + MAX_RESULTS]
    session.cursor += len(page_ids)
    cache = _get_retriever().place_cache
    places = [
        {**place, **session.annotations.get(place_id, {})}
        for place_id in page_ids
        if (place := cache.get_by_id(place_id)) is not None
    ]
    return ChatResponse(
        language=language,
        answer=SEE_MORE_LINE[language],
        results=_place_results(places),
        turns_left=session.turns_left,
        has_more=session.cursor < len(session.ranked_ids),
        debug={"answer_source": "see_more"},
    )


def _place_results(places: list[dict]) -> list[PlaceResult]:
    results: list[PlaceResult] = []
    for place in places:
        try:
            place_dict = place.copy()
            loc = place_dict.get("location")
            if isinstance(loc, dict) and loc.get("lat") is not None and loc.get("lng") is not None:
                place_dict["location"] = LatLng(lat=loc["lat"], lng=loc["lng"])
            elif isinstance(loc, dict):
                place_dict["location"] = None
            results.append(PlaceResult(**place_dict))
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
    return results


async def _answer(
    question: str, places: list[dict], language: str, started_at: float
) -> tuple[str, str]:
    """(answer, source): the model's grounded answer, else the template.

    The model is called at most once, and not at all when nothing was found.
    """
    if places and daily_cap.take():
        try:
            text = await llm.summarize(question, places, language, started_at=started_at)
        except Exception:  # the visitor always gets an answer, whatever the model client does
            logger.exception("Model call failed unexpectedly; using the template")
            text = None
        if text is not None:
            catalog_titles = [p.get("title") or "" for p in get_catalog() or []]
            if llm.is_grounded(text, places, catalog_titles, question=question):
                return llm.strip_markers(text), "llm"
            logger.warning("Model answer named places outside the results; using the template")
    return _generate_answer(places, language), "template"


def _generate_answer(places: list[dict], language: str) -> str:
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

    lines: list[str] = []
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



# TEMPORARY (mvp-2 T23 diagnosis): echo the caller's own proxy headers. Removed in the next commit.
@router.get("/_proxy-headers", include_in_schema=False)
async def _proxy_headers(http_request: Request) -> dict:
    h = http_request.headers
    return {
        "x-forwarded-for": h.get("x-forwarded-for"),
        "cf-connecting-ip": h.get("cf-connecting-ip"),
        "true-client-ip": h.get("true-client-ip"),
        "x-real-ip": h.get("x-real-ip"),
        "socket": http_request.client.host if http_request.client else None,
        "TRUSTED_PROXY_HOPS": TRUSTED_PROXY_HOPS,
    }
