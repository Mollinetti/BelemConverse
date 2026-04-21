"""Diagnostic corpora for the intent classifier.

Two corpora are exposed:

- :data:`CORPUS_A_GOLDEN`: derived from ``tests/test_golden_queries.py``.
  Sparse (6 queries) but represents officially-supported product queries.
  EN + PT-BR mix.

- :data:`CORPUS_B_DIAGNOSTIC`: ~110 PT-BR-heavy queries hand-labeled across
  six failure classes (canonical, colloquial, typo, accent_omission,
  multi_intent, ambiguous). EN supplement is small and only used as a
  smoke check, per the PT-BR-first scoping decision.

Each query carries:

- ``id`` — short stable identifier for the report.
- ``query`` — raw user input (verbatim, including typos and missing accents).
- ``language`` — "pt-BR" or "en".
- ``expected_intents`` — set of acceptable primary intents. Multi-element
  when the query genuinely admits several; the classifier passes if its
  primary prediction is in this set.
- ``expected_category`` — the single primary category the classifier should
  pick. ``None`` for queries that should NOT trigger any category (rare).
- ``expected_proximity`` — what ``QueryPlanner.extract_proximity_intent``
  should return.
- ``expected_open_now`` — what ``QueryPlanner.extract_open_now`` should
  return (True or None; False is not in the contract).
- ``failure_class`` — taxonomy bucket so we can compute per-class accuracy.
- ``notes`` — short rationale for label choice; used in failure dumps.

Labels were chosen conservatively: when in doubt about acceptable intent,
the set is widened (e.g. ``{"location", "popularity"}``) rather than
forcing the classifier into a brittle 1-of-N choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set


@dataclass(frozen=True)
class DiagnosticQuery:
    id: str
    query: str
    language: str  # "pt-BR" | "en"
    expected_intents: Set[str]
    expected_category: Optional[str]
    expected_proximity: bool
    expected_open_now: Optional[bool]  # True or None (legacy contract: never False)
    failure_class: str  # canonical | colloquial | typo | accent_omission | multi_intent | ambiguous
    notes: str = ""


# ---------------------------------------------------------------------------
# CORPUS A — golden queries derived from tests/test_golden_queries.py
# ---------------------------------------------------------------------------

CORPUS_A_GOLDEN = [
    DiagnosticQuery(
        id="A-Q1", query="Closest restaurants open now", language="en",
        expected_intents={"location", "business_hours"},
        expected_category="restaurant",
        expected_proximity=True, expected_open_now=True,
        failure_class="canonical",
        notes="Golden Q1 — distance + open_now + restaurant",
    ),
    DiagnosticQuery(
        id="A-Q2", query="Best rated sushi near me open now", language="en",
        expected_intents={"location", "popularity", "business_hours"},
        expected_category="restaurant",
        expected_proximity=True, expected_open_now=True,
        failure_class="multi_intent",
        notes="Golden Q2 — three intents (popularity wins for sort), restaurant",
    ),
    DiagnosticQuery(
        id="A-Q3", query="Popular bars within 1km", language="en",
        expected_intents={"popularity", "location"},
        expected_category="bar",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
        notes="Golden Q3 — popularity + proximity, bar",
    ),
    DiagnosticQuery(
        id="A-P1", query="Restaurantes mais próximos abertos agora", language="pt-BR",
        expected_intents={"location", "business_hours"},
        expected_category="restaurant",
        expected_proximity=True, expected_open_now=True,
        failure_class="canonical",
        notes="Golden P1 — canonical PT-BR proximity + open_now",
    ),
    DiagnosticQuery(
        id="A-P2", query="Melhores cafés perto de mim", language="pt-BR",
        expected_intents={"popularity", "location"},
        expected_category="cafe",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
        notes="Golden P2 — popularity + proximity, cafe",
    ),
    DiagnosticQuery(
        id="A-P3", query="Parque perto de mim aberto agora", language="pt-BR",
        expected_intents={"location", "business_hours"},
        expected_category="tourist_attraction",
        expected_proximity=True, expected_open_now=True,
        failure_class="canonical",
        notes="Golden P3 — proximity + open_now, parque maps to tourist_attraction",
    ),
]


# ---------------------------------------------------------------------------
# CORPUS B — diagnostic corpus (PT-BR heavy, with EN supplement)
# ---------------------------------------------------------------------------
# Organised by failure_class so it's obvious where coverage is concentrated.

# --- canonical (well-formed PT-BR; baseline accuracy) ---
_CANONICAL = [
    DiagnosticQuery(
        id="B-C01", query="restaurante perto de mim", language="pt-BR",
        expected_intents={"location"}, expected_category="restaurant",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C02", query="melhor pizzaria da região", language="pt-BR",
        expected_intents={"popularity"}, expected_category="restaurant",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
        notes="'da regiao' is a soft proximity signal in PT-BR",
    ),
    DiagnosticQuery(
        id="B-C03", query="açaí mais barato perto daqui", language="pt-BR",
        expected_intents={"price", "location"}, expected_category="acai",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C04", query="farmácia aberta agora", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="health",
        expected_proximity=False, expected_open_now=True,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C05", query="roteiro de um dia em Belém", language="pt-BR",
        expected_intents={"tour_planning"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C06", query="hotel perto do aeroporto", language="pt-BR",
        expected_intents={"location"}, expected_category="hotel",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C07", query="padaria 24 horas", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="cafe",
        expected_proximity=False, expected_open_now=True,
        failure_class="canonical",
        notes="padaria → cafe in classifier lexicon",
    ),
    DiagnosticQuery(
        id="B-C08", query="academia mais próxima", language="pt-BR",
        expected_intents={"location"}, expected_category="wellness",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C09", query="clínica veterinária próxima", language="pt-BR",
        expected_intents={"location"}, expected_category="pets",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C10", query="balada com música ao vivo hoje", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="nightlife",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
        notes="'hoje' alone is not a Strategy-1 open_now phrase",
    ),
    DiagnosticQuery(
        id="B-C11", query="oficina mecânica perto de casa", language="pt-BR",
        expected_intents={"location"}, expected_category="automotive",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C12", query="salão de beleza com manicure e pedicure", language="pt-BR",
        expected_intents={"popularity", "location", "verification"}, expected_category="beauty",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
        notes="No proximity signal — bare service request",
    ),
    DiagnosticQuery(
        id="B-C13", query="brinquedoteca com parquinho", language="pt-BR",
        expected_intents={"popularity", "location", "verification"}, expected_category="kids",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C14", query="quadra de tênis no clube", language="pt-BR",
        expected_intents={"popularity", "location", "verification"}, expected_category="sports",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-C15", query="ainda tem aquela cafeteria na frente?", language="pt-BR",
        expected_intents={"verification"}, expected_category="cafe",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
    ),
]

# --- colloquial (Brazilian slang and casual register) ---
_COLLOQUIAL = [
    DiagnosticQuery(
        id="B-S01", query="tem um boteco massa por aqui pra tomar uma gelada?", language="pt-BR",
        expected_intents={"location"}, expected_category="bar",
        expected_proximity=True, expected_open_now=None,
        failure_class="colloquial",
        notes="boteco=bar, massa=cool, gelada=cold beer; 'por aqui' is proximity",
    ),
    DiagnosticQuery(
        id="B-S02", query="bora dar um rolê no shopping", language="pt-BR",
        expected_intents={"location", "popularity"}, expected_category="shopping",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="'dar um rolê' = go hang out; no explicit proximity",
    ),
    DiagnosticQuery(
        id="B-S03", query="quero comer açaí gostoso", language="pt-BR",
        expected_intents={"popularity"}, expected_category="acai",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="'gostoso' implies popularity/quality",
    ),
    DiagnosticQuery(
        id="B-S04", query="onde eu tomo uma cerveja com a galera?", language="pt-BR",
        expected_intents={"location"}, expected_category="bar",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="'onde' is location intent but no explicit proximity word",
    ),
    DiagnosticQuery(
        id="B-S05", query="tem festa hoje em algum lugar?", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="nightlife",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="'hoje' is temporal not strict open_now phrase",
    ),
    DiagnosticQuery(
        id="B-S06", query="minha sobrancelha tá precisando", language="pt-BR",
        expected_intents={"verification", "popularity"}, expected_category="beauty",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="Implicit beauty service request — no explicit intent",
    ),
    DiagnosticQuery(
        id="B-S07", query="tô com fome, quero comer alguma coisa boa", language="pt-BR",
        expected_intents={"popularity"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="No explicit category keyword — relies on classifier inference",
    ),
    DiagnosticQuery(
        id="B-S08", query="quero malhar, tem academia perto?", language="pt-BR",
        expected_intents={"location"}, expected_category="wellness",
        expected_proximity=True, expected_open_now=None,
        failure_class="colloquial",
        notes="'malhar' = work out (slang)",
    ),
    DiagnosticQuery(
        id="B-S09", query="bora num churrasco hoje à noite", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="churrasco → churrascaria → restaurant",
    ),
    DiagnosticQuery(
        id="B-S10", query="cadê uma barbearia bacana aqui pertinho?", language="pt-BR",
        expected_intents={"location"}, expected_category="beauty",
        expected_proximity=True, expected_open_now=None,
        failure_class="colloquial",
        notes="'cadê' = onde; 'pertinho' is diminutive of perto (NOT in keyword list — coverage gap)",
    ),
    DiagnosticQuery(
        id="B-S11", query="alguma lanchonete da hora aberta agora?", language="pt-BR",
        expected_intents={"popularity", "business_hours"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=True,
        failure_class="colloquial",
        notes="'da hora' = cool",
    ),
    DiagnosticQuery(
        id="B-S12", query="quero curtir uma noitada com música ao vivo", language="pt-BR",
        expected_intents={"popularity"}, expected_category="nightlife",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="'noitada' = night out",
    ),
    DiagnosticQuery(
        id="B-S13", query="me indica um rodízio que valha a pena", language="pt-BR",
        expected_intents={"popularity"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
    ),
    DiagnosticQuery(
        id="B-S14", query="sabe alguma pousada aconchegante aqui pertinho?", language="pt-BR",
        expected_intents={"location", "popularity"}, expected_category="hotel",
        expected_proximity=True, expected_open_now=None,
        failure_class="colloquial",
        notes="'pertinho' diminutive — known gap; pousada → hotel",
    ),
    DiagnosticQuery(
        id="B-S15", query="quero levar as crianças num lugar legal", language="pt-BR",
        expected_intents={"popularity"}, expected_category="kids",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
    ),
    DiagnosticQuery(
        id="B-S16", query="tem um lava jato decente por aqui?", language="pt-BR",
        expected_intents={"location"}, expected_category="automotive",
        expected_proximity=True, expected_open_now=None,
        failure_class="colloquial",
    ),
    DiagnosticQuery(
        id="B-S17", query="onde compro ração pro meu cachorro?", language="pt-BR",
        expected_intents={"location"}, expected_category="pets",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
        notes="'onde' is location intent without explicit proximity",
    ),
    DiagnosticQuery(
        id="B-S18", query="quero relaxar, alguma massagem boa?", language="pt-BR",
        expected_intents={"popularity"}, expected_category="wellness",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
    ),
    DiagnosticQuery(
        id="B-S19", query="bora ver uma exposição esse fim de semana", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
    ),
    DiagnosticQuery(
        id="B-S20", query="lugar bom pra tomar um café da manhã reforçado", language="pt-BR",
        expected_intents={"popularity"}, expected_category="cafe",
        expected_proximity=False, expected_open_now=None,
        failure_class="colloquial",
    ),
]

# --- typo (common Portuguese typos: doubled/dropped letters, transposed) ---
_TYPO = [
    DiagnosticQuery(
        id="B-T01", query="restaurnte aberto agora", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=True,
        failure_class="typo",
        notes="restaurante → restaurnte (dropped 'a')",
    ),
    DiagnosticQuery(
        id="B-T02", query="academai perto de mim", language="pt-BR",
        expected_intents={"location"}, expected_category="wellness",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="academia → academai (transposed)",
    ),
    DiagnosticQuery(
        id="B-T03", query="farmcia 24 horas", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="health",
        expected_proximity=False, expected_open_now=True,
        failure_class="typo",
        notes="farmacia → farmcia (dropped 'a')",
    ),
    DiagnosticQuery(
        id="B-T04", query="cabelereira na regiao", language="pt-BR",
        expected_intents={"location"}, expected_category="beauty",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="cabeleireira → cabelereira (very common typo)",
    ),
    DiagnosticQuery(
        id="B-T05", query="veterenario perto", language="pt-BR",
        expected_intents={"location"}, expected_category="pets",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="veterinario → veterenario",
    ),
    DiagnosticQuery(
        id="B-T06", query="petshop perto deki", language="pt-BR",
        expected_intents={"location"}, expected_category="pets",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="daki → deki (typo on slang)",
    ),
    DiagnosticQuery(
        id="B-T07", query="lanchonte barata", language="pt-BR",
        expected_intents={"price"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="typo",
        notes="lanchonete → lanchonte",
    ),
    DiagnosticQuery(
        id="B-T08", query="padaira aberta agora", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="cafe",
        expected_proximity=False, expected_open_now=True,
        failure_class="typo",
        notes="padaria → padaira",
    ),
    DiagnosticQuery(
        id="B-T09", query="sorvetria proxima", language="pt-BR",
        expected_intents={"location"}, expected_category="ice_cream",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="sorveteria → sorvetria",
    ),
    DiagnosticQuery(
        id="B-T10", query="mecanca perto de mim", language="pt-BR",
        expected_intents={"location"}, expected_category="automotive",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="mecanica → mecanca",
    ),
    DiagnosticQuery(
        id="B-T11", query="pizaria barata", language="pt-BR",
        expected_intents={"price"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="typo",
        notes="pizzaria → pizaria",
    ),
    DiagnosticQuery(
        id="B-T12", query="sushiy aberto agora", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=True,
        failure_class="typo",
        notes="sushi → sushiy (extra letter)",
    ),
    DiagnosticQuery(
        id="B-T13", query="hotell barato proximo", language="pt-BR",
        expected_intents={"price", "location"}, expected_category="hotel",
        expected_proximity=True, expected_open_now=None,
        failure_class="typo",
        notes="hotel → hotell",
    ),
    DiagnosticQuery(
        id="B-T14", query="parqu da cidade", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="typo",
        notes="parque → parqu",
    ),
    DiagnosticQuery(
        id="B-T15", query="bairo bom pra comer", language="pt-BR",
        expected_intents={"popularity"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="typo",
        notes="bairro → bairo",
    ),
]

# --- accent_omission (correct spelling minus accents — extremely common in chat) ---
_ACCENT = [
    DiagnosticQuery(
        id="B-A01", query="acai cremoso e barato", language="pt-BR",
        expected_intents={"price"}, expected_category="acai",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
        notes="açaí → acai (the keyword list already includes 'acai')",
    ),
    DiagnosticQuery(
        id="B-A02", query="farmacia aberta hoje", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="health",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
        notes="farmácia → farmacia; 'hoje' alone is not Strategy-1 open_now",
    ),
    DiagnosticQuery(
        id="B-A03", query="academia mais proxima", language="pt-BR",
        expected_intents={"location"}, expected_category="wellness",
        expected_proximity=True, expected_open_now=None,
        failure_class="accent_omission",
        notes="próxima → proxima",
    ),
    DiagnosticQuery(
        id="B-A04", query="musica ao vivo hoje a noite", language="pt-BR",
        expected_intents={"business_hours", "popularity"}, expected_category="nightlife",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
    ),
    DiagnosticQuery(
        id="B-A05", query="cafe da manha", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="cafe",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
        notes="café → cafe; both forms in keyword list",
    ),
    DiagnosticQuery(
        id="B-A06", query="estadio para assistir jogo", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="sports",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
    ),
    DiagnosticQuery(
        id="B-A07", query="ginasio com piscina", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="wellness",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
    ),
    DiagnosticQuery(
        id="B-A08", query="confeitaria proxima a mim", language="pt-BR",
        expected_intents={"location"}, expected_category="cafe",
        expected_proximity=True, expected_open_now=None,
        failure_class="accent_omission",
    ),
    DiagnosticQuery(
        id="B-A09", query="otimo restaurante para almoco", language="pt-BR",
        expected_intents={"popularity"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
        notes="ótimo → otimo, almoço → almoco",
    ),
    DiagnosticQuery(
        id="B-A10", query="ponto turistico famoso", language="pt-BR",
        expected_intents={"popularity"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="accent_omission",
        notes="turístico → turistico",
    ),
]

# --- multi_intent (deliberately combine 2-4 intents in one query) ---
_MULTI = [
    DiagnosticQuery(
        id="B-M01", query="melhor restaurante barato aberto agora perto de mim", language="pt-BR",
        expected_intents={"popularity", "price", "business_hours", "location"},
        expected_category="restaurant",
        expected_proximity=True, expected_open_now=True,
        failure_class="multi_intent",
        notes="4 intents — known stress test for multi-label",
    ),
    DiagnosticQuery(
        id="B-M02", query="açaí cremoso barato 24 horas", language="pt-BR",
        expected_intents={"popularity", "price", "business_hours"},
        expected_category="acai",
        expected_proximity=False, expected_open_now=True,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M03", query="academia barata perto pra começar musculação", language="pt-BR",
        expected_intents={"price", "location"}, expected_category="wellness",
        expected_proximity=True, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M04", query="petshop barato pra banho e tosa do meu cachorro", language="pt-BR",
        expected_intents={"price"}, expected_category="pets",
        expected_proximity=False, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M05", query="balada com show ao vivo essa noite com open bar", language="pt-BR",
        expected_intents={"business_hours", "popularity"}, expected_category="nightlife",
        expected_proximity=False, expected_open_now=None,
        failure_class="multi_intent",
        notes="'open bar' is nightlife jargon, NOT Strategy-1 open_now",
    ),
    DiagnosticQuery(
        id="B-M06", query="restaurante japonês top perto daqui aberto agora barato", language="pt-BR",
        expected_intents={"popularity", "location", "business_hours", "price"},
        expected_category="restaurant",
        expected_proximity=True, expected_open_now=True,
        failure_class="multi_intent",
        notes="4 intents",
    ),
    DiagnosticQuery(
        id="B-M07", query="hotel 5 estrelas com piscina perto da praia", language="pt-BR",
        expected_intents={"popularity", "location"}, expected_category="hotel",
        expected_proximity=True, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M08", query="cabeleireira boa e barata aqui perto", language="pt-BR",
        expected_intents={"popularity", "price", "location"}, expected_category="beauty",
        expected_proximity=True, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M09", query="oficina mecânica 24h perto que faça troca de óleo", language="pt-BR",
        expected_intents={"location", "business_hours"}, expected_category="automotive",
        expected_proximity=True, expected_open_now=True,
        failure_class="multi_intent",
        notes="'24h' should map to 'aberto 24'-style intent (likely a gap)",
    ),
    DiagnosticQuery(
        id="B-M10", query="parque infantil grátis com brinquedoteca perto de casa", language="pt-BR",
        expected_intents={"price", "location"}, expected_category="kids",
        expected_proximity=True, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M11", query="igreja histórica famosa para visitar", language="pt-BR",
        expected_intents={"popularity"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M12", query="dentista 24 horas de emergência", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="health",
        expected_proximity=False, expected_open_now=True,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M13", query="quadra de futebol pra alugar hoje à noite", language="pt-BR",
        expected_intents={"business_hours"}, expected_category="sports",
        expected_proximity=False, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M14", query="loja de roupa famosa no shopping", language="pt-BR",
        expected_intents={"popularity"}, expected_category="shopping",
        expected_proximity=False, expected_open_now=None,
        failure_class="multi_intent",
    ),
    DiagnosticQuery(
        id="B-M15", query="cinema barato pra hoje à noite", language="pt-BR",
        expected_intents={"price"}, expected_category="entertainment",
        expected_proximity=False, expected_open_now=None,
        failure_class="multi_intent",
    ),
]

# --- ambiguous (no explicit category keyword; classifier must infer) ---
_AMBIGUOUS = [
    DiagnosticQuery(
        id="B-X01", query="tem onde dormir aqui?", language="pt-BR",
        expected_intents={"location"}, expected_category="hotel",
        expected_proximity=True, expected_open_now=None,
        failure_class="ambiguous",
        notes="'dormir' implies hotel; 'aqui' is proximity",
    ),
    DiagnosticQuery(
        id="B-X02", query="preciso de um lugar pra ficar essa semana", language="pt-BR",
        expected_intents={"verification"}, expected_category="hotel",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="No keyword for hotel — purely semantic",
    ),
    DiagnosticQuery(
        id="B-X03", query="quero ir num lugar bonito pra tirar fotos", language="pt-BR",
        expected_intents={"popularity"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
    ),
    DiagnosticQuery(
        id="B-X04", query="onde eu compro uma carteira de couro?", language="pt-BR",
        expected_intents={"location"}, expected_category="shopping",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="'compro' should signal shopping",
    ),
    DiagnosticQuery(
        id="B-X05", query="alguém pra cuidar do meu cachorro de fim de semana", language="pt-BR",
        expected_intents={"verification"}, expected_category="pets",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
    ),
    DiagnosticQuery(
        id="B-X06", query="preciso comprar remédio pra dor de cabeça", language="pt-BR",
        expected_intents={"verification"}, expected_category="health",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="remédio → farmacia → health",
    ),
    DiagnosticQuery(
        id="B-X07", query="estou com fome", language="pt-BR",
        expected_intents={"verification", "popularity"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="No keyword at all — pure semantic challenge",
    ),
    DiagnosticQuery(
        id="B-X08", query="quero relaxar de verdade hoje", language="pt-BR",
        expected_intents={"popularity"}, expected_category="wellness",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="'relaxar' implies wellness but no explicit category keyword",
    ),
    DiagnosticQuery(
        id="B-X09", query="alguma coisa divertida pra fazer com as crianças", language="pt-BR",
        expected_intents={"popularity"}, expected_category="kids",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
    ),
    DiagnosticQuery(
        id="B-X10", query="quero conhecer a cidade hoje", language="pt-BR",
        expected_intents={"tour_planning"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="'conhecer' is verification keyword AND tourism intent",
    ),
    DiagnosticQuery(
        id="B-X11", query="quero algo gelado e doce", language="pt-BR",
        expected_intents={"popularity"}, expected_category="ice_cream",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="No keyword — implicit ice cream",
    ),
    DiagnosticQuery(
        id="B-X12", query="quero ir numa boate diferente hoje", language="pt-BR",
        expected_intents={"popularity"}, expected_category="nightlife",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
    ),
    # ----- P1 extension: ambiguous queries the F5 lexicon should now catch -----
    DiagnosticQuery(
        id="B-X13", query="preciso pernoitar essa semana", language="pt-BR",
        expected_intents={"verification"}, expected_category="hotel",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — 'pernoitar' is in implicit lexicon for hotel",
    ),
    DiagnosticQuery(
        id="B-X14", query="estou estressado e cansado de tudo", language="pt-BR",
        expected_intents={"verification", "popularity"}, expected_category="wellness",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — implicit wellness without keyword",
    ),
    DiagnosticQuery(
        id="B-X15", query="quero comprar um sapato novo", language="pt-BR",
        expected_intents={"verification"}, expected_category="shopping",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — 'comprar um sapato' is in implicit lexicon",
    ),
    DiagnosticQuery(
        id="B-X16", query="preciso de uma consulta médica urgente", language="pt-BR",
        expected_intents={"verification"}, expected_category="health",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — 'consulta medica' is in implicit lexicon",
    ),
    DiagnosticQuery(
        id="B-X17", query="lugar legal pra brincar com meus filhos", language="pt-BR",
        expected_intents={"popularity"}, expected_category="kids",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — implicit kids; 'lugar pra meu filho' in lexicon",
    ),
    DiagnosticQuery(
        id="B-X18", query="quero tomar um geladinho de coco", language="pt-BR",
        expected_intents={"popularity", "verification"}, expected_category="ice_cream",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 + F7 — 'geladinho de coco' in lexicon, ice_cream rebalanced",
    ),
    DiagnosticQuery(
        id="B-X19", query="tomar uma cerveja gelada com os amigos", language="pt-BR",
        expected_intents={"verification", "popularity"}, expected_category="bar",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — 'tomar uma cerveja' in lexicon",
    ),
    DiagnosticQuery(
        id="B-X20", query="preciso dar um trato no visual antes da festa", language="pt-BR",
        expected_intents={"verification"}, expected_category="beauty",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — 'dar um trato no visual' in lexicon",
    ),
    DiagnosticQuery(
        id="B-X21", query="meu carro tá fazendo barulho estranho", language="pt-BR",
        expected_intents={"verification"}, expected_category="automotive",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — 'carro fazendo barulho' in lexicon",
    ),
    DiagnosticQuery(
        id="B-X22", query="lugar bacana pra um happy hour aqui pertinho", language="pt-BR",
        expected_intents={"location", "popularity"}, expected_category="bar",
        expected_proximity=True, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 + F6 — happy hour lexicon + pertinho proximity diminutive",
    ),
]

# --- EN supplement (small smoke check; PT-BR is the priority) ---
_EN_SMOKE = [
    DiagnosticQuery(
        id="B-E01", query="cheap pizza near me", language="en",
        expected_intents={"price", "location"}, expected_category="restaurant",
        expected_proximity=True, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-E02", query="best coffee shop downtown", language="en",
        expected_intents={"popularity"}, expected_category="cafe",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-E03", query="24 hour pharmacy open right now", language="en",
        expected_intents={"business_hours"}, expected_category="health",
        expected_proximity=False, expected_open_now=True,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-E04", query="things to do in Belém in one day", language="en",
        expected_intents={"tour_planning"}, expected_category="tourist_attraction",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
    ),
    DiagnosticQuery(
        id="B-E05", query="best gym with pool nearby", language="en",
        expected_intents={"popularity", "location"}, expected_category="wellness",
        expected_proximity=True, expected_open_now=None,
        failure_class="multi_intent",
    ),
    # ----- P1 EN extension: thin coverage of the categories the lexicon now teaches -----
    DiagnosticQuery(
        id="B-E06", query="i need a place to stay tonight", language="en",
        expected_intents={"verification"}, expected_category="hotel",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — EN implicit hotel",
    ),
    DiagnosticQuery(
        id="B-E07", query="where can i get a massage to relax", language="en",
        expected_intents={"location"}, expected_category="wellness",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — EN implicit wellness",
    ),
    DiagnosticQuery(
        id="B-E08", query="i'm hungry, where should i eat", language="en",
        expected_intents={"location", "verification"}, expected_category="restaurant",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 — EN implicit restaurant via 'hungry'",
    ),
    DiagnosticQuery(
        id="B-E09", query="best ice cream shop in the area", language="en",
        expected_intents={"popularity"}, expected_category="ice_cream",
        expected_proximity=False, expected_open_now=None,
        failure_class="canonical",
        notes="P1/F7 — ice_cream rebalanced",
    ),
    DiagnosticQuery(
        id="B-E10", query="grab a beer with friends downtown", language="en",
        expected_intents={"verification", "popularity"}, expected_category="bar",
        expected_proximity=False, expected_open_now=None,
        failure_class="ambiguous",
        notes="P1/F5 + F7 — EN implicit bar via 'grab a beer'",
    ),
]


CORPUS_B_DIAGNOSTIC = (
    _CANONICAL + _COLLOQUIAL + _TYPO + _ACCENT + _MULTI + _AMBIGUOUS + _EN_SMOKE
)


# Convenience: full combined corpus for the harness
ALL_QUERIES = CORPUS_A_GOLDEN + CORPUS_B_DIAGNOSTIC
