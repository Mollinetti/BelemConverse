"""mvp-1: the model benchmark runs golden questions through retrieval + summarize."""

import json

import httpx

from belem_converse.tools import bench_llm


def test_bench_reports_grounding_and_latency(built_catalog, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://bench.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "bench-key")
    # The golden questions are located around the real city; these two retrieve
    # fixture places, so each one reaches the model.
    monkeypatch.setattr(
        bench_llm,
        "_questions",
        lambda: [
            ("restaurantes em Belém", "pt-BR", None),
            ("lugares bem avaliados", "pt-BR", None),
            ("academia de musculação", "pt-BR", None),  # beyond queries=2
        ],
    )
    models_seen = []

    def handler(request):
        models_seen.append(json.loads(request.content)["model"])
        # Names no place, so it is grounded whatever the fixture retrieves.
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Separei algumas opções para você."}}]}
        )

    rows = bench_llm.run(
        models=["fake"], queries=2, catalog=built_catalog, transport=httpx.MockTransport(handler)
    )

    (row,) = rows
    assert row["model"] == "fake"
    assert row["n"] == 2
    assert row["grounded_pct"] == 100
    assert row["p50_ms"] >= 0
    assert models_seen == ["fake", "fake"]
