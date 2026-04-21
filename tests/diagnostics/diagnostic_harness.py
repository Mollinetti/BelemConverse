"""Diagnostic harness for the SimpleTFIDFIntentClassifier.

Runs the classifier and the QueryPlanner extractors against the diagnostic
corpora, computes accuracy / precision / recall / F1 per intent and category,
records latency, and uses a custom log handler to capture the structured
instrumentation events (``proximity_intent_detection``, ``open_now_detection``,
``category_detection``) for an agreement analysis between the keyword
strategies and the classifier.

Output:

- A JSON artifact at ``tests/diagnostics/reports/diagnostic_results.json``
  with raw per-query data.
- A markdown report at ``tests/diagnostics/reports/diagnostic_report.md``
  with aggregated metrics, failure breakdowns, and the agreement matrix.

This module is intentionally **not** a pytest test — pytest would surface
each diagnostic failure as a CI failure, and the diagnostic is meant to
quantify imperfection, not enforce it. Run via :mod:`run_diagnostic`.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
    SimpleTFIDFIntentClassifier,
)
from belem_converse.core.query_planner import QueryPlanner

from tests.diagnostics.diagnostic_corpus import (
    ALL_QUERIES,
    CORPUS_A_GOLDEN,
    CORPUS_B_DIAGNOSTIC,
    DiagnosticQuery,
)


# ---------------------------------------------------------------------------
# Log capture for instrumentation events
# ---------------------------------------------------------------------------


class _InstrumentationCapture(logging.Handler):
    """Captures the three structured instrumentation events emitted by the
    QueryPlanner. Indexed by event name → list of ``LogRecord.__dict__`` slices.

    Only fields known to be set by the production code are captured, to keep
    the JSON artifact stable.
    """

    EVENT_NAMES = {
        "proximity_intent_detection",
        "open_now_detection",
        "category_detection",
    }

    PROXIMITY_FIELDS = (
        "query", "language", "strategy1_hit", "strategy1_signal",
        "strategy2_hit", "agree", "result",
    )
    OPEN_NOW_FIELDS = (
        "query", "language", "strategy1_hit", "strategy1_signal",
        "strategy2_hit", "agree", "result",
    )
    CATEGORY_FIELDS = (
        "query", "language", "classifier_status", "classifier_top_category",
        "classifier_top_confidence", "classifier_high_conf_categories",
        "keyword_match_categories", "keyword_match_count",
        # P1/F5 — Strategy 0 (implicit-category lexicon) instrumentation.
        "strategy0_categories", "strategy0_phrases", "strategy0_lexicon_status",
        "agree", "agree_strategy12", "agree_strategy01",
        "result_count",
    )

    def __init__(self) -> None:
        super().__init__()
        self.events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def emit(self, record: logging.LogRecord) -> None:
        if record.msg not in self.EVENT_NAMES:
            return
        if record.msg == "proximity_intent_detection":
            fields = self.PROXIMITY_FIELDS
        elif record.msg == "open_now_detection":
            fields = self.OPEN_NOW_FIELDS
        else:
            fields = self.CATEGORY_FIELDS
        snapshot = {f: getattr(record, f, None) for f in fields}
        self.events[record.msg].append(snapshot)

    def reset(self) -> None:
        self.events = defaultdict(list)


# ---------------------------------------------------------------------------
# Per-query result
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    id: str
    query: str
    language: str
    failure_class: str

    expected_intents: List[str]
    expected_category: Optional[str]
    expected_proximity: bool
    expected_open_now: Optional[bool]

    predicted_intent: str
    predicted_intent_confidence: float
    predicted_top3_intents: List[Dict[str, float]]
    predicted_category: str
    predicted_category_confidence: float
    predicted_top3_categories: List[Dict[str, float]]

    proximity_returned: bool
    open_now_returned: Optional[bool]
    categories_returned_count: int

    intent_correct: bool
    category_correct: bool
    proximity_correct: bool
    open_now_correct: bool

    latency_ms_intent: float
    latency_ms_category: float
    latency_ms_total: float

    instrumentation_proximity: Optional[Dict[str, Any]] = None
    instrumentation_open_now: Optional[Dict[str, Any]] = None
    instrumentation_category: Optional[Dict[str, Any]] = None

    notes: str = ""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _load_classifier() -> SimpleTFIDFIntentClassifier:
    """Load the classifier (training is cached via the pickled model file)."""
    clf = SimpleTFIDFIntentClassifier()
    clf.train()
    return clf


def _run_single(
    q: DiagnosticQuery,
    classifier: SimpleTFIDFIntentClassifier,
    planner: QueryPlanner,
    capture: _InstrumentationCapture,
) -> QueryResult:
    capture.reset()

    t0_total = time.perf_counter()

    t0 = time.perf_counter()
    intent_pred = classifier.predict_intent(q.query)
    t_intent_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    cat_pred = classifier.predict_category(q.query)
    t_cat_ms = (time.perf_counter() - t0) * 1000

    proximity_returned = planner.extract_proximity_intent(q.query, q.language)
    open_now_returned = planner.extract_open_now(q.query, q.language)
    categories_returned = planner.extract_categories(q.query, q.language)

    t_total_ms = (time.perf_counter() - t0_total) * 1000

    predicted_intent = intent_pred.get("primary_intent", "unknown")
    predicted_category = cat_pred.get("primary_category", "")

    intent_ok = predicted_intent in q.expected_intents
    category_ok = (
        q.expected_category is None
        or predicted_category == q.expected_category
    )
    proximity_ok = proximity_returned == q.expected_proximity
    open_now_ok = open_now_returned == q.expected_open_now

    return QueryResult(
        id=q.id,
        query=q.query,
        language=q.language,
        failure_class=q.failure_class,
        expected_intents=sorted(q.expected_intents),
        expected_category=q.expected_category,
        expected_proximity=q.expected_proximity,
        expected_open_now=q.expected_open_now,
        predicted_intent=predicted_intent,
        predicted_intent_confidence=float(intent_pred.get("primary_confidence", 0)),
        predicted_top3_intents=[
            {"intent": i["intent"], "confidence": float(i["confidence"])}
            for i in intent_pred.get("intents", [])
        ],
        predicted_category=predicted_category,
        predicted_category_confidence=float(cat_pred.get("primary_confidence", 0)),
        predicted_top3_categories=[
            {"category": c["category"], "confidence": float(c["confidence"])}
            for c in cat_pred.get("categories", [])
        ],
        proximity_returned=proximity_returned,
        open_now_returned=open_now_returned,
        categories_returned_count=len(categories_returned),
        intent_correct=intent_ok,
        category_correct=category_ok,
        proximity_correct=proximity_ok,
        open_now_correct=open_now_ok,
        latency_ms_intent=t_intent_ms,
        latency_ms_category=t_cat_ms,
        latency_ms_total=t_total_ms,
        instrumentation_proximity=(
            capture.events["proximity_intent_detection"][-1]
            if capture.events.get("proximity_intent_detection") else None
        ),
        instrumentation_open_now=(
            capture.events["open_now_detection"][-1]
            if capture.events.get("open_now_detection") else None
        ),
        instrumentation_category=(
            capture.events["category_detection"][-1]
            if capture.events.get("category_detection") else None
        ),
        notes=q.notes,
    )


def run() -> Tuple[List[QueryResult], Dict[str, Any]]:
    """Run the full diagnostic. Returns (per_query_results, aggregate_metrics)."""
    classifier = _load_classifier()
    planner = QueryPlanner(intent_classifier=classifier)

    capture = _InstrumentationCapture()
    capture.setLevel(logging.INFO)
    qp_logger = logging.getLogger("belem_converse.core.query_planner")
    prior_level = qp_logger.level
    qp_logger.setLevel(logging.INFO)
    qp_logger.addHandler(capture)

    try:
        results = [_run_single(q, classifier, planner, capture) for q in ALL_QUERIES]
    finally:
        qp_logger.removeHandler(capture)
        qp_logger.setLevel(prior_level)

    aggregate = _aggregate(results)
    return results, aggregate


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _per_label_prf(
    results: List[QueryResult], get_pred: callable, get_expected_set: callable
) -> Dict[str, Dict[str, float]]:
    """Compute per-label precision/recall/F1 treating each label independently.

    A prediction is a True Positive for label L when:
    - get_pred(r) == L AND L in get_expected_set(r)

    A prediction is a False Positive for label L when:
    - get_pred(r) == L AND L not in get_expected_set(r)

    A False Negative for label L is when:
    - L in get_expected_set(r) AND get_pred(r) != L
    (Note: when expected is multi-element, only one of them can be matched
    by a single primary prediction, so the missed ones count as FN. This is
    a strict interpretation; a multi-label classifier could do better.)
    """
    labels = set()
    for r in results:
        labels.add(get_pred(r))
        labels.update(get_expected_set(r))
    labels.discard("")
    labels.discard("unknown")

    metrics = {}
    for label in sorted(labels):
        tp = fp = fn = 0
        for r in results:
            pred = get_pred(r)
            expected = get_expected_set(r)
            if pred == label:
                if label in expected:
                    tp += 1
                else:
                    fp += 1
            else:
                if label in expected:
                    fn += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        metrics[label] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }
    return metrics


def _confusion_matrix(
    results: List[QueryResult], get_pred: callable, get_expected: callable
) -> Dict[str, Dict[str, int]]:
    """Build a confusion matrix using the FIRST expected label as the row.

    For multi-label expected sets we use the first element (alphabetical order
    in the corpus's sorted serialization) as the canonical 'gold' label. This
    is a known simplification — the per-label PRF metrics above are the more
    rigorous view.
    """
    matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        gold = get_expected(r)
        pred = get_pred(r)
        if gold:
            matrix[gold][pred or "(empty)"] += 1
    return {k: dict(v) for k, v in matrix.items()}


def _aggregate(results: List[QueryResult]) -> Dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    # Overall accuracy
    intent_acc = sum(r.intent_correct for r in results) / n
    cat_acc = sum(r.category_correct for r in results) / n
    prox_acc = sum(r.proximity_correct for r in results) / n
    open_acc = sum(r.open_now_correct for r in results) / n

    # Per-failure-class breakdown
    by_class: Dict[str, Dict[str, Any]] = {}
    for cls in sorted({r.failure_class for r in results}):
        subset = [r for r in results if r.failure_class == cls]
        by_class[cls] = {
            "n": len(subset),
            "intent_acc": round(sum(r.intent_correct for r in subset) / len(subset), 3),
            "category_acc": round(sum(r.category_correct for r in subset) / len(subset), 3),
            "proximity_acc": round(sum(r.proximity_correct for r in subset) / len(subset), 3),
            "open_now_acc": round(sum(r.open_now_correct for r in subset) / len(subset), 3),
        }

    # Per-language breakdown
    by_lang: Dict[str, Dict[str, Any]] = {}
    for lang in sorted({r.language for r in results}):
        subset = [r for r in results if r.language == lang]
        by_lang[lang] = {
            "n": len(subset),
            "intent_acc": round(sum(r.intent_correct for r in subset) / len(subset), 3),
            "category_acc": round(sum(r.category_correct for r in subset) / len(subset), 3),
            "proximity_acc": round(sum(r.proximity_correct for r in subset) / len(subset), 3),
            "open_now_acc": round(sum(r.open_now_correct for r in subset) / len(subset), 3),
        }

    # Per-corpus breakdown
    a_ids = {q.id for q in CORPUS_A_GOLDEN}
    by_corpus = {}
    for name, ids in [("corpus_a_golden", a_ids), ("corpus_b_diagnostic", {q.id for q in CORPUS_B_DIAGNOSTIC})]:
        subset = [r for r in results if r.id in ids]
        if subset:
            by_corpus[name] = {
                "n": len(subset),
                "intent_acc": round(sum(r.intent_correct for r in subset) / len(subset), 3),
                "category_acc": round(sum(r.category_correct for r in subset) / len(subset), 3),
                "proximity_acc": round(sum(r.proximity_correct for r in subset) / len(subset), 3),
                "open_now_acc": round(sum(r.open_now_correct for r in subset) / len(subset), 3),
            }

    # Per-label PRF
    intent_prf = _per_label_prf(
        results,
        get_pred=lambda r: r.predicted_intent,
        get_expected_set=lambda r: set(r.expected_intents),
    )
    category_prf = _per_label_prf(
        results,
        get_pred=lambda r: r.predicted_category,
        get_expected_set=lambda r: {r.expected_category} if r.expected_category else set(),
    )

    # Confusion matrices (rows = first expected label, cols = predicted)
    intent_cm = _confusion_matrix(
        results,
        get_pred=lambda r: r.predicted_intent,
        get_expected=lambda r: r.expected_intents[0] if r.expected_intents else "",
    )
    category_cm = _confusion_matrix(
        results,
        get_pred=lambda r: r.predicted_category,
        get_expected=lambda r: r.expected_category or "",
    )

    # Latency
    intent_latencies = sorted(r.latency_ms_intent for r in results)
    cat_latencies = sorted(r.latency_ms_category for r in results)
    total_latencies = sorted(r.latency_ms_total for r in results)

    def _percentile(xs, p):
        if not xs:
            return 0.0
        k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
        return round(xs[k], 3)

    latency = {
        "intent_ms_p50": _percentile(intent_latencies, 50),
        "intent_ms_p95": _percentile(intent_latencies, 95),
        "category_ms_p50": _percentile(cat_latencies, 50),
        "category_ms_p95": _percentile(cat_latencies, 95),
        "total_ms_p50": _percentile(total_latencies, 50),
        "total_ms_p95": _percentile(total_latencies, 95),
    }

    # Instrumentation agreement stats
    prox_events = [r.instrumentation_proximity for r in results if r.instrumentation_proximity]
    open_events = [r.instrumentation_open_now for r in results if r.instrumentation_open_now]
    cat_events = [r.instrumentation_category for r in results if r.instrumentation_category]

    def _agreement_breakdown(events, hit_a="strategy1_hit", hit_b="strategy2_hit"):
        counts = Counter()
        for e in events:
            a = bool(e.get(hit_a))
            b = bool(e.get(hit_b))
            counts[(a, b)] += 1
        return {
            "both_hit": counts[(True, True)],
            "only_strategy1": counts[(True, False)],
            "only_strategy2": counts[(False, True)],
            "neither": counts[(False, False)],
            "agree_rate": round(
                (counts[(True, True)] + counts[(False, False)]) / max(1, sum(counts.values())),
                3,
            ),
        }

    cat_agree_counts = Counter(
        e.get("agree") for e in cat_events
    )

    instrumentation = {
        "proximity": _agreement_breakdown(prox_events),
        "open_now": _agreement_breakdown(open_events),
        "category": {
            "agree_true": cat_agree_counts.get(True, 0),
            "agree_false": cat_agree_counts.get(False, 0),
            "agree_none": cat_agree_counts.get(None, 0),
            "agree_rate_when_decidable": round(
                cat_agree_counts.get(True, 0)
                / max(1, cat_agree_counts.get(True, 0) + cat_agree_counts.get(False, 0)),
                3,
            ),
        },
    }

    return {
        "n": n,
        "overall": {
            "intent_acc": round(intent_acc, 3),
            "category_acc": round(cat_acc, 3),
            "proximity_acc": round(prox_acc, 3),
            "open_now_acc": round(open_acc, 3),
        },
        "by_corpus": by_corpus,
        "by_failure_class": by_class,
        "by_language": by_lang,
        "intent_prf": intent_prf,
        "category_prf": category_prf,
        "intent_confusion_matrix": intent_cm,
        "category_confusion_matrix": category_cm,
        "latency": latency,
        "instrumentation": instrumentation,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _md_table(headers: List[str], rows: List[List[Any]]) -> str:
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    head = "| " + " | ".join(headers) + " |"
    body = "\n".join(
        "| " + " | ".join(str(c) for c in row) + " |" for row in rows
    )
    return "\n".join([head, sep, body])


def render_markdown(results: List[QueryResult], aggregate: Dict[str, Any]) -> str:
    """Render the human-readable markdown report."""
    lines: List[str] = []
    lines.append("# Intent Classifier Diagnostic Report")
    lines.append("")
    lines.append(
        "Generated by `tests/diagnostics/diagnostic_harness.py`. "
        "All metrics are computed against the hand-labeled corpora in "
        "`tests/diagnostics/diagnostic_corpus.py` (Corpus A = 6 golden queries "
        "derived from `tests/test_golden_queries.py`; Corpus B = 92 PT-BR-heavy "
        "diagnostic queries spanning canonical / colloquial / typo / accent_omission / "
        "multi_intent / ambiguous failure classes)."
    )
    lines.append("")

    # Overall
    o = aggregate["overall"]
    lines.append("## 1. Overall accuracy")
    lines.append("")
    lines.append(_md_table(
        ["Metric", "Accuracy"],
        [
            ["intent (primary in expected set)", f"{o['intent_acc']:.1%}"],
            ["category (primary == expected)", f"{o['category_acc']:.1%}"],
            ["extract_proximity_intent", f"{o['proximity_acc']:.1%}"],
            ["extract_open_now", f"{o['open_now_acc']:.1%}"],
        ],
    ))
    lines.append("")
    lines.append(f"_n = {aggregate['n']} queries_")
    lines.append("")

    # By corpus
    lines.append("## 2. Accuracy by corpus")
    lines.append("")
    rows = []
    for name, m in aggregate["by_corpus"].items():
        rows.append([
            name, m["n"],
            f"{m['intent_acc']:.1%}", f"{m['category_acc']:.1%}",
            f"{m['proximity_acc']:.1%}", f"{m['open_now_acc']:.1%}",
        ])
    lines.append(_md_table(
        ["corpus", "n", "intent", "category", "proximity", "open_now"], rows,
    ))
    lines.append("")

    # By failure class
    lines.append("## 3. Accuracy by failure class (Corpus B taxonomy)")
    lines.append("")
    rows = []
    for cls, m in aggregate["by_failure_class"].items():
        rows.append([
            cls, m["n"],
            f"{m['intent_acc']:.1%}", f"{m['category_acc']:.1%}",
            f"{m['proximity_acc']:.1%}", f"{m['open_now_acc']:.1%}",
        ])
    lines.append(_md_table(
        ["failure_class", "n", "intent", "category", "proximity", "open_now"], rows,
    ))
    lines.append("")

    # By language
    lines.append("## 4. Accuracy by language")
    lines.append("")
    rows = []
    for lang, m in aggregate["by_language"].items():
        rows.append([
            lang, m["n"],
            f"{m['intent_acc']:.1%}", f"{m['category_acc']:.1%}",
            f"{m['proximity_acc']:.1%}", f"{m['open_now_acc']:.1%}",
        ])
    lines.append(_md_table(
        ["language", "n", "intent", "category", "proximity", "open_now"], rows,
    ))
    lines.append("")

    # Intent PRF
    lines.append("## 5. Per-intent precision / recall / F1")
    lines.append("")
    lines.append(
        "Strict interpretation: a single primary prediction is the only credit. "
        "Multi-element expected sets (e.g. `{location, popularity}`) count as a "
        "false negative for every expected label that the primary prediction did not match."
    )
    lines.append("")
    rows = []
    for label, m in aggregate["intent_prf"].items():
        rows.append([
            label, m["support"], m["tp"], m["fp"], m["fn"],
            f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}",
        ])
    lines.append(_md_table(
        ["intent", "support", "TP", "FP", "FN", "P", "R", "F1"], rows,
    ))
    lines.append("")

    # Category PRF
    lines.append("## 6. Per-category precision / recall / F1")
    lines.append("")
    rows = []
    for label, m in aggregate["category_prf"].items():
        rows.append([
            label, m["support"], m["tp"], m["fp"], m["fn"],
            f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}",
        ])
    lines.append(_md_table(
        ["category", "support", "TP", "FP", "FN", "P", "R", "F1"], rows,
    ))
    lines.append("")

    # Confusion matrices
    lines.append("## 7. Intent confusion matrix (rows = first expected, cols = predicted)")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(aggregate["intent_confusion_matrix"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    lines.append("## 8. Category confusion matrix (rows = expected, cols = predicted)")
    lines.append("")
    lines.append("```")
    lines.append(json.dumps(aggregate["category_confusion_matrix"], indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")

    # Latency
    lines.append("## 9. Latency")
    lines.append("")
    rows = []
    for k, v in aggregate["latency"].items():
        rows.append([k, f"{v} ms"])
    lines.append(_md_table(["metric", "value"], rows))
    lines.append("")

    # Instrumentation agreement
    lines.append("## 10. Strategy-1 vs Strategy-2 agreement (from instrumentation logs)")
    lines.append("")
    inst = aggregate["instrumentation"]

    lines.append("### 10.1 extract_proximity_intent")
    lines.append("")
    p = inst["proximity"]
    lines.append(_md_table(
        ["bucket", "n"],
        [
            ["both strategies hit", p["both_hit"]],
            ["only Strategy 1 (keywords) hit", p["only_strategy1"]],
            ["only Strategy 2 (classifier) hit", p["only_strategy2"]],
            ["neither hit", p["neither"]],
            ["agree rate", f"{p['agree_rate']:.1%}"],
        ],
    ))
    lines.append("")

    lines.append("### 10.2 extract_open_now")
    lines.append("")
    p = inst["open_now"]
    lines.append(_md_table(
        ["bucket", "n"],
        [
            ["both strategies hit", p["both_hit"]],
            ["only Strategy 1 (keywords) hit", p["only_strategy1"]],
            ["only Strategy 2 (classifier) hit", p["only_strategy2"]],
            ["neither hit", p["neither"]],
            ["agree rate", f"{p['agree_rate']:.1%}"],
        ],
    ))
    lines.append("")

    lines.append("### 10.3 extract_categories")
    lines.append("")
    p = inst["category"]
    lines.append(_md_table(
        ["bucket", "n"],
        [
            ["agree (classifier top is in keyword-matched set)", p["agree_true"]],
            ["disagree", p["agree_false"]],
            ["undecidable (one or both empty)", p["agree_none"]],
            ["agree rate (when decidable)", f"{p['agree_rate_when_decidable']:.1%}"],
        ],
    ))
    lines.append("")

    # Failure dump
    lines.append("## 11. Per-query failure dump")
    lines.append("")
    lines.append(
        "Listed only when at least one of the four checks failed. Sorted by "
        "failure class then by id. Useful for hand-inspection."
    )
    lines.append("")
    failures = [
        r for r in results
        if not (r.intent_correct and r.category_correct and r.proximity_correct and r.open_now_correct)
    ]
    failures.sort(key=lambda r: (r.failure_class, r.id))
    rows = []
    for r in failures:
        bad = []
        if not r.intent_correct:
            bad.append(f"intent={r.predicted_intent}({r.predicted_intent_confidence:.2f})∉{r.expected_intents}")
        if not r.category_correct:
            bad.append(f"cat={r.predicted_category}≠{r.expected_category}")
        if not r.proximity_correct:
            bad.append(f"prox={r.proximity_returned}≠{r.expected_proximity}")
        if not r.open_now_correct:
            bad.append(f"open={r.open_now_returned}≠{r.expected_open_now}")
        rows.append([r.failure_class, r.id, r.query, " · ".join(bad)])
    if rows:
        lines.append(_md_table(["class", "id", "query", "failures"], rows))
    else:
        lines.append("_No failures._")
    lines.append("")

    # Notes block
    lines.append("## 12. Methodology notes")
    lines.append("")
    lines.append(
        "- **Multi-label expected intents**: a single-class classifier evaluated against a "
        "multi-element expected set is given credit if the primary prediction is in the set. "
        "Per-label PRF (Section 5) uses a stricter accounting that counts every missed expected "
        "label as a false negative."
    )
    lines.append(
        "- **Open-now contract**: the production code returns `True` or `None`, never `False`. "
        "Diagnostic labels respect that, so `expected_open_now=None` covers both 'silent' and 'should-not-fire'."
    )
    lines.append(
        "- **Latency**: measured around `predict_intent` and `predict_category` plus the three "
        "`extract_*` methods on the QueryPlanner. Cold-start (model load) is excluded — the "
        "classifier is loaded once before the loop."
    )
    lines.append(
        "- **Instrumentation logs**: captured via a custom `logging.Handler` attached to "
        "`belem_converse.core.query_planner` at `INFO` level. Three event names are captured: "
        "`proximity_intent_detection`, `open_now_detection`, `category_detection`."
    )
    lines.append("")

    return "\n".join(lines)


def write_artifacts(
    results: List[QueryResult],
    aggregate: Dict[str, Any],
    out_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """Write the JSON + markdown artifacts to ``out_dir``. Returns the two paths."""
    if out_dir is None:
        out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "diagnostic_results.json"
    md_path = out_dir / "diagnostic_report.md"

    payload = {
        "aggregate": aggregate,
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    md_path.write_text(render_markdown(results, aggregate))

    return json_path, md_path
