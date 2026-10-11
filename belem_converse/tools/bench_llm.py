"""Benchmark candidate models on the golden questions.

    python -m belem_converse.tools.bench_llm MODEL [MODEL ...] [--queries N] [--catalog PATH]

Each golden question goes through the same planner → retriever → top 5 path
as the API, then to ``llm.summarize``; the answer is checked with
``llm.is_grounded``. The provider comes from LLM_BASE_URL / LLM_API_KEY, and
each MODEL replaces LLM_MODEL for its run. Prints a markdown table (grounded
share, median model latency) and every pt-BR answer for the Portuguese
spot-check. Run from the repo root: the questions live in
tests/test_golden_queries.py.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from pathlib import Path

import httpx

from belem_converse import llm
from belem_converse.catalog import load_places
from belem_converse.cities import get_city_config
from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.query_planner import QueryPlanner
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever
from belem_converse.utils.config import DATA_DIR

MAX_RESULTS = 5


def _questions() -> list[tuple]:
    from tests.test_golden_queries import GOLDEN_QUERIES_EN, GOLDEN_QUERIES_PT

    return [(q["query"], "pt-BR", q.get("location")) for q in GOLDEN_QUERIES_PT] + [
        (q["query"], "en", q.get("location")) for q in GOLDEN_QUERIES_EN
    ]


def _retrieve_all(catalog: Path, questions: list[tuple]) -> tuple[list[tuple], list[str]]:
    """(question, language, top places) for each question, plus all catalog titles."""
    places = load_places(catalog)
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    planner = QueryPlanner(intent_classifier=classifier)
    retriever = UnifiedRetriever(
        place_cache=PlaceCache(places),
        category_matcher=CategoryMatcher(classifier),
        ranking_engine=RankingEngine(),
    )
    retrieved = []
    for question, language, location in questions:
        plan = planner.create_query_plan(question, user_location=location, explicit_language=language)
        result = retriever.retrieve(
            {
                "intent": plan.intent,
                "slots": plan.slots,
                "retrieval_strategy": "structured_only",
                "proximity_intent_detected": plan.slots.get("proximity_intent_detected", False),
                "language": plan.language,
            }
        )
        retrieved.append((question, language, result.places[:MAX_RESULTS]))
    return retrieved, [p["title"] or "" for p in places]


def run(
    models: list[str],
    queries: int | None = None,
    catalog: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[dict]:
    """One row per model: model, n, grounded_pct, p50_ms, answers."""
    catalog = catalog or DATA_DIR / get_city_config().catalog_path
    questions = _questions()[:queries] if queries else _questions()
    retrieved, catalog_titles = _retrieve_all(catalog, questions)

    rows = []
    original_model = os.environ.get("LLM_MODEL")
    try:
        for model in models:
            os.environ["LLM_MODEL"] = model  # summarize reads it per call
            latencies, answers = [], []
            for question, language, places in retrieved:
                if not places:
                    continue  # the API never calls the model with nothing to describe
                start = time.perf_counter()
                answer = asyncio.run(llm.summarize(question, places, language, transport=transport))
                latencies.append((time.perf_counter() - start) * 1000)
                grounded = answer is not None and llm.is_grounded(answer, places, catalog_titles)
                answers.append({"question": question, "language": language, "answer": answer, "grounded": grounded})
            n = len(answers)
            rows.append(
                {
                    "model": model,
                    "n": n,
                    "grounded_pct": round(100 * sum(a["grounded"] for a in answers) / n, 1) if n else 0.0,
                    "p50_ms": round(statistics.median(latencies)) if latencies else None,
                    "answers": answers,
                }
            )
    finally:
        if original_model is None:
            os.environ.pop("LLM_MODEL", None)
        else:
            os.environ["LLM_MODEL"] = original_model
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", nargs="+", help="model names to benchmark on the configured provider")
    parser.add_argument("--queries", type=int, default=None, help="only the first N golden questions")
    parser.add_argument("--catalog", type=Path, default=None, help="places.sqlite (default: the city's catalog)")
    args = parser.parse_args(argv)

    rows = run(args.models, args.queries, args.catalog)
    print("| Model | n | Grounded % | p50 latency (ms) |")
    print("|---|---|---|---|")
    for row in rows:
        print(f"| {row['model']} | {row['n']} | {row['grounded_pct']} | {row['p50_ms']} |")
    for row in rows:
        print(f"\n## {row['model']} — pt-BR answers")
        for a in row["answers"]:
            if a["language"] == "pt-BR":
                mark = "ok" if a["grounded"] else "NOT GROUNDED"
                print(f"- [{mark}] {a['question']}\n  {a['answer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
