# Intent Classifier Improvement Plan

> Status: **Proposal** — no code changes outside of the diagnostic harness and
> the three QueryPlanner instrumentation events have been applied as part of
> this document. All recommendations below are *unimplemented*.
>
> Constraint: **no LLM calls** in any recommendation. Every proposal must be
> trainable and runnable on CPU within the existing latency budget
> (currently `predict_intent` p95 ≈ 0.18 ms; `predict_category` p95 ≈ 0.18 ms).

## 0. Where this came from

The classifier in
`belem_converse/classifiers/intent_classifier_TFIDF_simple.py`
(`SimpleTFIDFIntentClassifier`, model `v2.7`) was evaluated against two
hand-labeled corpora living at
`tests/diagnostics/diagnostic_corpus.py`:

- **Corpus A** — 6 golden queries derived from `tests/test_golden_queries.py`.
- **Corpus B** — 92 PT-BR-heavy queries hand-labeled across six failure
  classes: `canonical`, `colloquial`, `typo`, `accent_omission`,
  `multi_intent`, `ambiguous`.

The harness at `tests/diagnostics/diagnostic_harness.py` runs:

- `classifier.predict_intent` and `classifier.predict_category`
- `QueryPlanner.extract_proximity_intent`, `extract_open_now`, `extract_categories`

…against every query and computes per-label PRF, confusion matrices,
per-failure-class accuracy, latency, and an agreement analysis sourced
from the three structured instrumentation events (`proximity_intent_detection`,
`open_now_detection`, `category_detection`) that ship in production code.

Reproduce with:

```bash
python -m tests.diagnostics.run_diagnostic
```

Reports land in `tests/diagnostics/reports/`.

## 1. Headline numbers

| Metric | Accuracy | Verdict |
| --- | --- | --- |
| `extract_proximity_intent` | **93.9%** | Healthy. Strategy-1 OR Strategy-2 OR is robust. |
| `extract_open_now` | **94.9%** | Healthy. Same architecture as proximity. |
| `predict_intent` (primary in expected set) | **74.5%** | Borderline; `verification` is broken. |
| `predict_category` | **60.2%** | **Unhealthy.** Driven by one phantom-label bug + typo blindness. |

Latency is not a constraint: median classifier call is ~0.15 ms.

The boolean extractors carry their own keyword fallback, which is why they
score well above the underlying `predict_intent`. **The brittleness lives in
the ML side, and `extract_categories` inherits it directly because it has no
fallback for the primary-category choice.**

## 2. The five failure modes that explain everything

### F1 — phantom `popularity` category (root cause: training-data poisoning)

> Severity: **Critical.** Single biggest contributor to category misclassification.

**Symptom.** The category classifier predicts `popularity` 26 times across
the 98-query corpus despite `popularity` not being a category at all.
Per-category PRF: `popularity` has support=0, FP=26, F1=0.

**Cause.** `_prepare_simple_training_data` is called for both the intent
keyword set AND the category keyword set (`train()`, lines 487 and 492).
At the bottom of the function it unconditionally appends
`location_negatives` with `y.append('popularity')`
(line 471). For the **intent** classifier this is fine — `popularity` is a
valid intent label. For the **category** classifier it injects a phantom
category with rich training signal that absorbs almost any compound query
mentioning multiple service words ("salao com cabeleireiro manicure pedicure",
"academia com spa sauna massagem", etc.).

**Failures it causes.** B-S04, B-S07, B-S12, B-S15, B-S18, B-S19, B-X02,
B-X04 through B-X09, B-C12, B-C13, B-C14, B-C10, B-M14 — at least 15 of
the 39 category misses.

**Fix (P0).** Split the training-data preparation: pass an
`include_location_negatives: bool` flag, default True for the intent
classifier and False for the category classifier. Or move the negatives
out of `_prepare_simple_training_data` entirely and inject them only at
the intent-classifier `fit` site. Bump `MODEL_VERSION` to force a retrain.

**Expected impact.** +15 to +20 percentage points on overall category
accuracy. Eliminates ~26 FPs on a non-existent label.

---

### F2 — `verification` intent over-fires (root cause: keyword grab-bag)

> Severity: **Critical.** Worst per-intent F1 in the table.

**Symptom.** `verification` PRF: P=0.125, R=0.133, F1=0.129. Confusion
matrix shows `verification` is the predicted bucket for 8 `popularity` queries,
3 `business_hours` queries, 3 `business_hours`, 2 `price`, 1 `tour_planning`.

**Cause.** The `verification` intent's keyword list
(`intent_keywords['verification']`, lines 64–84 of the classifier) is a
30+ entry grab-bag including extremely generic phrases:

- `'is the'`, `'does the'`, `'where is the'`, `'looking for'`, `'find'`,
  `'encontrar'`, `'tem'`, `'há'`, `'has'`, `'have'`, `'currently'`,
  `'atualmente'`, `'nowadays'`

These are not verification signals — they are basic question/search words
that appear in nearly every conversational query. The TF-IDF weights for
these tokens become diagnostic of "verification" purely because no other
intent's templates use them.

**Failures it causes.** Most of the `ambiguous` failure-class drop
(intent_acc=16.7%); B-S03, B-S05, B-S15, B-A02, B-A04, B-A10, B-X01, B-X03,
B-X08, B-X10, B-X11, B-X12, B-T07, B-T11.

**Fix (P0).** Trim the `verification` keyword list to only true existence-
check phrases: `'does exist'`, `'still exists'`, `'ainda existe'`,
`'ainda funciona'`, `'still open'`, `'closed down'`, `'shut down'`,
`'fechou'`, `'encerrou'`, `'verificar se'`, `'confirmar se'`, `'check if'`,
`'is it true'`, `'é verdade'`, `'ouvi dizer'`, `'still there'`,
`'ainda tem'`. **Drop everything else.**

**Expected impact.** +5 to +10 pp on overall intent accuracy. Lifts
`popularity` recall (currently 0.50) by 0.10–0.15 because the popularity
queries it currently steals will route correctly.

---

### F3 — typo blindness (root cause: word-only TF-IDF, no char features)

> Severity: **High.** Touches an explicit user-provided requirement
> (typos and edge cases must be tolerated).

**Symptom.** Typo failure-class category accuracy is **46.7%** — almost a
coin flip. Confusion matrix shows that one-letter typos make the message
"feel like" `restaurant` (the highest-prior category) to the classifier,
because none of the typoed tokens appear in any lexicon.

**Cause.** Both vectorizers use `TfidfVectorizer(ngram_range=(1, 2),
lowercase=True)` — word and word-bigram features only. `"academia"`
and `"academai"` share zero word features.

**Fix (P0).** Build an ensemble:

```python
self.intent_vectorizer = FeatureUnion([
    ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=500)),
    ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=1000)),
])
```

`char_wb (3, 5)` over `"academia"` produces e.g. `acad`, `cade`, `adem`,
`demi`, `emia`, of which `"academai"` shares 4. Same trick for the
category vectorizer.

**Expected impact.** +25 to +35 pp on the typo failure class.
Negligible latency increase (TF-IDF + LogisticRegression is dominated by
sparse multiplication; `char_wb (3,5)` adds ~2,000 nonzero features
per query).

**Caveat.** Char features can also smear category boundaries
(e.g. `"sushi"` and `"sushiy"` correctly merge but `"sorvete"` and
`"sorveter"` will share substring with `"resterveter…"`-type strings).
Mitigated by ensembling with the word features rather than replacing.

---

### F4 — open_now misses bare "24h" / "24 horas"

> Severity: Medium. Causes 3 of the 5 multi_intent open_now failures.

**Symptom.** Queries `"açaí cremoso barato 24 horas"`,
`"oficina mecânica 24h perto que faça troca de óleo"`,
`"dentista 24 horas de emergência"` all return `open_now=None` (expected
`True`).

**Cause.** `_OPEN_NOW_PHRASES` includes `'aberto 24'` and `'aberto 24 horas'`
but **not** the bare forms `'24 horas'` or `'24h'`. The classifier doesn't
help because none of these queries trigger `business_hours` as primary
intent (popularity / location win).

**Fix (P0).** Append to `_OPEN_NOW_PHRASES`:

```
'24 horas', '24h', '24hr', 'vinte e quatro horas',
'24/7', 'round the clock', 'todos os dias 24',
```

**Expected impact.** Fixes the 3 listed failures and any future "24h"-style
queries. Risk: false-positive on queries like *"aberto durante 24 dias"* —
acceptable given the rarity of that phrasing.

---

### F5 — semantic queries with no surface keyword

> Severity: High. Drives the `ambiguous` failure-class drop (intent_acc=16.7%,
> category_acc=25%). Hardest to fix without LLMs.

**Symptom.** Queries with no category keyword at all — `"estou com fome"` →
expected `restaurant`, gets `popularity`. `"tem onde dormir aqui?"` →
expected `hotel`, gets `restaurant`. `"alguma coisa divertida pra fazer
com as crianças"` → expected `kids`, gets `popularity`.

**Cause.** TF-IDF on synthetic templated training data has zero signal for
any of these phrasings. `"fome"`, `"dormir"`, `"divertida"`, `"comprar"`,
`"relaxar"` are nowhere in the lexicon.

**Fix (P1, no-LLM).** A two-pronged approach:

1. **Implicit-category lexicon** (rule-based). Add a tiny dictionary in
   the classifier mapping semantic anchors to categories:

   ```python
   IMPLICIT_CATEGORY_MAP = {
       'restaurant': ['fome', 'comer', 'comida', 'almocar', 'jantar'],
       'hotel': ['dormir', 'pernoitar', 'ficar a noite', 'pra ficar',
                 'lugar pra ficar'],
       'wellness': ['relaxar', 'descansar', 'me sentir melhor',
                    'estresse', 'cansado'],
       'shopping': ['comprar', 'compras', 'adquirir'],
       'kids': ['com as criancas', 'pras criancas', 'pra crianca'],
       'tourist_attraction': ['conhecer a cidade', 'ver pontos',
                              'tirar foto', 'visitar lugares'],
       'pets': ['cuidar do meu cachorro', 'pro meu cachorro',
                'meu pet'],
   }
   ```

   Apply in `extract_categories` BEFORE the keyword scan, with lower
   priority than direct keyword matches.

2. **Synthetic semantic templates in training data**. Add a handful of
   semantic phrases per category to `_prepare_simple_training_data`:

   ```python
   semantic_examples = {
       'restaurant': ['estou com fome', 'quero comer alguma coisa',
                      'to com fome quero comer'],
       'hotel': ['preciso de um lugar pra ficar',
                 'tem onde dormir aqui'],
       'wellness': ['quero relaxar de verdade',
                    'preciso descansar'],
       ...
   }
   ```

**Expected impact.** Lifts `ambiguous` class accuracy from 25% → 65–75%.
This is a known ceiling for cheap NLP; getting closer to 90% requires
embeddings (see F8).

---

## 3. Secondary findings

### F6 — diminutives and slang typos in proximity (small)

`pertinho` (diminutive of `perto`), `deki` (typo of `daki`) — not in the
proximity word/phrase lists. The classifier still catches these via the
`location` intent, so the boolean answer is right, but the
instrumentation log shows `only_strategy2` hits we'd rather have agreed
on. Add `'pertinho', 'aqui pertinho', 'aí pertinho', 'deki'` to
`_PROXIMITY_PHRASES` / `_PROXIMITY_WORDS` (P1, S effort).

### F7 — `popularity` predictions on canonical queries

Even after fixing F1, the canonical category accuracy (58.3%) is dragged
by queries like `"brinquedoteca com parquinho"` → predicted `popularity`,
`"quadra de tênis no clube"` → `popularity`. These have correct keywords
in the message; the classifier should weight them. After F1's fix this
will partially heal, but a deeper review of the per-category training
template counts is warranted (kids, sports, shopping have sparse training
data relative to restaurant). (P1, M effort.)

### F8 — semantic embeddings (no-LLM ceiling lift)

For the irreducible `ambiguous` failure mode, the long-term path without
LLMs is **pretrained static word embeddings** (FastText PT-BR, ~700 MB or
the smaller `cc.pt.300.bin` quantized to ~300 MB; `gensim` loads in
~5 s). Compute mean-pooled embedding for the query and cosine-similarity
against per-category prototype embeddings (mean of category-keyword
embeddings). Add this as a third strategy in `extract_categories`.
Inference cost: ~3–5 ms/query. (P2, L effort.)

### F9 — multi-label intent output

`predict_intent` already returns top-3 with confidence ≥ 0.2, but the
QueryPlanner consumes only `primary_intent`. For `multi_intent` queries,
this loses information — e.g. *"melhor restaurante barato aberto agora
perto de mim"* should fan out to `popularity`, `price`, `business_hours`,
`location`. The boolean extractors already query the classifier
independently; the missing piece is `extract_sort_preference` and any
future signals consuming all detected intents. (P1, M effort.)

### F10 — confidence calibration

The classifier ships uncalibrated probabilities from LogisticRegression.
The `≥ 0.3` thresholds in `extract_categories` are heuristic. After the
P0 fixes, run isotonic regression on a held-out set to calibrate
`predict_proba` outputs so the thresholds become statistically meaningful.
(P1, S effort.)

### F11 — active-learning loop from production logs

The three new structured events (`proximity_intent_detection`,
`open_now_detection`, `category_detection`) carry the per-strategy hit
flags. Mining for `agree=False` cases identifies real-world queries where
the classifier and the keyword fallback diverge — these are the highest-
leverage queries to hand-label and add to the next training set.
Recommended cadence: monthly batch of 50 disagreement queries → label →
add to a `tests/diagnostics/training_supplements.py` → retrain → ship a
new `MODEL_VERSION`. (P2, M effort, ongoing.)

### F12 — real query corpus (long-term)

Once the app has been in production for a while, sample 1,000 unique
queries from logs, hand-label, and use as the **primary** training
signal, demoting the synthetic templates to a regularization role. This
is the highest-impact change long-term but requires real traffic.
(P2, L effort, contingent on production usage.)

---

## 4. Phased plan

### P0 — quick wins (S effort, days)

| # | Item | Impact (est) | LOC |
| --- | --- | --- | --- |
| F1 | Stop poisoning category classifier with `popularity` negatives | category +15-20 pp | ~20 |
| F2 | Trim `verification` keyword list to existence-only phrases | intent +5-10 pp; lifts popularity recall | ~30 |
| F3 | Add `char_wb (3,5)` ensemble vectorizer | typo class +25-35 pp; overall +5-10 pp | ~15 |
| F4 | Add bare 24h / 24 horas to `_OPEN_NOW_PHRASES` | open_now +3-5 pp on multi_intent | ~5 |

**P0 total expected uplift**: intent ~74.5% → ~85%, category ~60% → ~80%.

### P1 — medium effort (weeks)

- F5 — implicit-category lexicon + semantic synthetic examples
- F6 — diminutives in proximity
- F7 — re-balance per-category training template counts
- F9 — multi-label intent consumption in QueryPlanner
- F10 — Platt / isotonic calibration

### P2 — large effort, long-term

- F8 — FastText embeddings as a third strategy
- F11 — active learning loop from instrumentation logs
- F12 — real query corpus (depends on production traffic)

---

## 5. What we are explicitly NOT recommending

Per the constraint, **no LLM call** appears in any recommendation.
Specifically rejected (correctly, in our view):

- **Sentence embeddings via a remote LLM API.** Even SBERT-style hosted
  endpoints would blow past the 0.18 ms latency budget and incur per-query
  cost.
- **Few-shot LLM intent classification.** Same.
- **LLM-based query rewriting before classification.** Same.

If at some point the latency / cost budget changes, the no-LLM ceiling is
likely to be ~85–90% on this corpus (constrained mostly by the `ambiguous`
class). LLMs would lift it to the high 90s but at 20–200× the per-query
cost.

---

## 6. Open questions

1. **MODEL_VERSION bump cadence.** P0 changes to training data require a
   `MODEL_VERSION` bump and a retrain; the existing v2.7 pickle should be
   regenerated. Should we ship a CI check that the model file matches the
   committed `MODEL_VERSION`?
2. **Training-data residency.** The implicit-category lexicon (F5) is
   regional (PT-BR Belém-flavored). Where should it live — inline in
   `intent_classifier_TFIDF_simple.py`, or in a JSON/YAML data file
   loaded at training time?
3. **Eval gate in CI.** Should the P0 metrics become a pytest gate
   (e.g. *intent ≥ 80%, category ≥ 75% on Corpus B*) blocking
   `MODEL_VERSION` bumps that regress?

---

_Last updated: with diagnostic harness output v1 (n=98 queries, model
v2.7). Re-run `python -m tests.diagnostics.run_diagnostic` after any
training change to refresh the report under
`tests/diagnostics/reports/`._
