"""
Standalone runner: executes all 30 Portuguese complex test scenarios and writes
a detailed log to portuguese_complex_results.log.

Run with:
    python generate_portuguese_log.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

TEST_LAT = -1.4557549
TEST_LON = -48.4901799
TEST_LOCATION = "Travessa Curuzu, 1475, Belem, PA"
USER_LOCATION = {'lat': TEST_LAT, 'lng': TEST_LON}

# ---------------------------------------------------------------------------
# All 30 test scenarios
# ---------------------------------------------------------------------------
SCENARIOS = [
    {
        "num": 1,
        "desc": "Erro de digitação - 'restarante' ao invés de 'restaurante'",
        "query": "restarante perto de mim",
        "expected_categories": ["restaurant"],
        "expected_filters": {"proximity_intent_detected": True},
    },
    {
        "num": 2,
        "desc": "Múltiplas categorias + filtros - pizza, hamburguer, comida italiana barata",
        "query": "quero pizza hamburguer ou comida italiana barata perto daqui",
        "expected_categories": ["pizza", "hamburguer", "italian"],
        "expected_filters": {"proximity_intent_detected": True, "price_max": "any"},
    },
    {
        "num": 3,
        "desc": "Frase coloquial mal formulada",
        "query": "ae mano tem algum bar restaurante com musica ao vivo aberto agora ai perto?",
        "expected_categories": ["bar", "restaurant", "musica"],
        "expected_filters": {"open_now": True, "proximity_intent_detected": True},
    },
    {
        "num": 4,
        "desc": "4 categorias misturadas - café, padaria, lanchonete, sorveteria",
        "query": "cafe padaria lanchonete ou sorveteria com bom preço em belem",
        "expected_categories": ["cafe", "padaria", "lanchonete", "sorveteria"],
        "expected_filters": {},
    },
    {
        "num": 5,
        "desc": "Múltiplos erros de digitação",
        "query": "resturante japones ou chines com entrga rapida e barato",
        "expected_categories": ["restaurant", "japones", "chines"],
        "expected_filters": {},
    },
    {
        "num": 6,
        "desc": "Combinação complexa de filtros",
        "query": "restaurante italiano ou frances aberto agora com nota acima de 4 estrelas e preço medio",
        "expected_categories": ["restaurant", "italian", "frances"],
        "expected_filters": {"open_now": True, "min_rating": "any"},
    },
    {
        "num": 7,
        "desc": "Gíria regional paraense",
        "query": "bora num bar massa pra tomar uma gelada e comer tira gosto",
        "expected_categories": ["bar"],
        "expected_filters": {},
    },
    {
        "num": 8,
        "desc": "Tour com múltiplas categorias",
        "query": "quero fazer um tour pelos museus parques e pontos turisticos de belem",
        "expected_categories": ["museu", "parque", "turistico"],
        "expected_filters": {"intent": "tour_planning"},
    },
    {
        "num": 9,
        "desc": "Mistura de proximidade e popularidade",
        "query": "os melhores restaurantes perto de mim",
        "expected_categories": ["restaurant"],
        "expected_filters": {"proximity_intent_detected": True},
    },
    {
        "num": 10,
        "desc": "Farmácia e hospital com urgência",
        "query": "preciso urgente de farmacia ou hospital aberto 24 horas aqui perto",
        "expected_categories": ["farmacia", "hospital"],
        "expected_filters": {"proximity_intent_detected": True},
    },
    {
        "num": 11,
        "desc": "Café da manhã, almoço e jantar",
        "query": "lugar pra cafe da manha almoco e jantar tudo no mesmo lugar",
        "expected_categories": ["cafe", "restaurant"],
        "expected_filters": {},
    },
    {
        "num": 12,
        "desc": "Erros de acentuação",
        "query": "restaurante japones proximo com rodizio de sushi e preco bom",
        "expected_categories": ["restaurant", "japones", "sushi"],
        "expected_filters": {"proximity_intent_detected": True},
    },
    {
        "num": 13,
        "desc": "Shopping, entretenimento e comida",
        "query": "shopping com cinema restaurante e loja de roupa tudo junto",
        "expected_categories": ["shopping", "cinema", "restaurant", "loja"],
        "expected_filters": {},
    },
    {
        "num": 14,
        "desc": "Frase muito mal formulada",
        "query": "tipo assim sabe aquele lugar q tem tipo comida boa e tal barato sabe perto daki",
        "expected_categories": [],
        "expected_filters": {"proximity_intent_detected": True, "price_max": "any"},
    },
    {
        "num": 15,
        "desc": "Pratos específicos múltiplos",
        "query": "onde tem açai tapioca e pastel perto da travessa curuzu",
        "expected_categories": ["acai", "tapioca", "pastel"],
        "expected_filters": {},
    },
    {
        "num": 16,
        "desc": "Academia, spa e bem-estar",
        "query": "academia com spa sauna e massagem incluso na mensalidade",
        "expected_categories": ["academia", "spa", "sauna", "massagem"],
        "expected_filters": {},
    },
    {
        "num": 17,
        "desc": "Serviços para pets múltiplos",
        "query": "petshop com veterinario banho tosa e hotel pra cachorro",
        "expected_categories": ["petshop", "veterinario"],
        "expected_filters": {},
    },
    {
        "num": 18,
        "desc": "Vida noturna com múltiplos locais",
        "query": "balada bar boate ou pub com musica ao vivo e pista de danca",
        "expected_categories": ["balada", "bar", "boate", "pub"],
        "expected_filters": {},
    },
    {
        "num": 19,
        "desc": "Educação com múltiplos tipos",
        "query": "escola de ingles espanhol frances e alemao perto de casa",
        "expected_categories": ["escola"],
        "expected_filters": {"proximity_intent_detected": True},
    },
    {
        "num": 20,
        "desc": "Serviços de saúde complexos",
        "query": "clinica com dentista dermatologista oftalmologista e exames de sangue",
        "expected_categories": ["clinica", "dentista"],
        "expected_filters": {},
    },
    {
        "num": 21,
        "desc": "Erros extremos de digitação",
        "query": "restavrante italianu ou mexikano kon entrega rapda e baratu",
        "expected_categories": ["restaurant"],
        "expected_filters": {},
    },
    {
        "num": 22,
        "desc": "Atividades de praia múltiplas",
        "query": "praia com restaurante bar quiosque e aluguel de cadeira e guarda sol",
        "expected_categories": ["praia", "restaurant", "bar", "quiosque"],
        "expected_filters": {},
    },
    {
        "num": 23,
        "desc": "Serviços automotivos múltiplos",
        "query": "oficina mecanica com borracharia funilaria pintura e lavagem",
        "expected_categories": ["oficina", "mecanica"],
        "expected_filters": {},
    },
    {
        "num": 24,
        "desc": "Serviços de beleza completos",
        "query": "salao de beleza com cabeleireiro manicure pedicure maquiagem e depilacao",
        "expected_categories": ["salao", "beleza", "cabeleireiro"],
        "expected_filters": {},
    },
    {
        "num": 25,
        "desc": "Culinária mista complexa",
        "query": "restaurante q serve comida brasileira japonesa italiana e arabe tudo no mesmo cardapio",
        "expected_categories": ["restaurant", "brasileira", "japonesa", "italiana", "arabe"],
        "expected_filters": {},
    },
    {
        "num": 26,
        "desc": "Entretenimento infantil múltiplo",
        "query": "lugar com brinquedoteca parquinho piscina de bolinha e festa infantil",
        "expected_categories": ["brinquedoteca", "parquinho"],
        "expected_filters": {},
    },
    {
        "num": 27,
        "desc": "Instalações esportivas múltiplas",
        "query": "clube com quadra de tenis futebol volei basquete e piscina olimpica",
        "expected_categories": ["clube", "quadra"],
        "expected_filters": {},
    },
    {
        "num": 28,
        "desc": "Locais culturais misturados",
        "query": "teatro cinema museu galeria de arte e centro cultural tudo perto",
        "expected_categories": ["teatro", "cinema", "museu", "galeria"],
        "expected_filters": {"proximity_intent_detected": True},
    },
    {
        "num": 29,
        "desc": "Serviços de entrega múltiplos",
        "query": "restaurante pizzaria lanchonete ou hamburgueria com entrega rapida gratis e aceita pix",
        "expected_categories": ["restaurant", "pizzaria", "lanchonete", "hamburgueria"],
        "expected_filters": {},
    },
    {
        "num": 30,
        "desc": "Atividades de fim de semana complexas",
        "query": "lugar pra levar a familia no fim de semana com restaurante parque playground e area de churrasco",
        "expected_categories": ["restaurant", "parque", "playground"],
        "expected_filters": {},
    },
]


def check_filter(key, expected_val, slots, intent):
    """Return (matched: bool, actual_val)."""
    if key == "intent":
        actual = intent
        return actual == expected_val, actual
    actual = slots.get(key)
    if expected_val == "any":
        return actual is not None, actual
    return actual == expected_val, actual


def run_all(planner):
    results = []
    passed = 0

    for sc in SCENARIOS:
        plan = planner.create_query_plan(message=sc["query"], user_location=USER_LOCATION)
        pd = planner.plan_to_dict(plan)
        slots = pd.get("slots", {})
        intent = pd.get("intent", "")
        categories_str = str(slots.get("categories", [])).lower()

        # Category checks
        cat_found = []
        cat_missing = []
        for cat in sc["expected_categories"]:
            if cat.lower() in categories_str:
                cat_found.append(cat)
            else:
                cat_missing.append(cat)

        # Filter checks
        filter_results = {}
        for fk, fv in sc["expected_filters"].items():
            matched, actual = check_filter(fk, fv, slots, intent)
            filter_results[fk] = {"expected": fv, "actual": actual, "ok": matched}

        all_filters_ok = all(v["ok"] for v in filter_results.values())
        test_passed = pd["language"] == "pt-BR" and all_filters_ok

        if test_passed:
            passed += 1

        results.append({
            "scenario": sc,
            "plan": pd,
            "slots": slots,
            "intent": intent,
            "cat_found": cat_found,
            "cat_missing": cat_missing,
            "filter_results": filter_results,
            "passed": test_passed,
        })

    return results, passed


def write_log(results, passed, log_path):
    total = len(results)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    sep = "=" * 120
    thin = "-" * 120

    lines.append(sep)
    lines.append("RELATÓRIO DE TESTES — CONSULTAS COMPLEXAS EM PORTUGUÊS")
    lines.append(f"Gerado em : {ts}")
    lines.append(f"Localização de Teste : {TEST_LOCATION}")
    lines.append(f"Coordenadas : lat={TEST_LAT}, lon={TEST_LON}")
    lines.append(f"Resultado Global : {passed}/{total} PASSOU")
    lines.append(sep)

    for r in results:
        sc = r["scenario"]
        pd = r["plan"]
        slots = r["slots"]
        status = "PASSOU ✓" if r["passed"] else "FALHOU ✗"

        lines.append("")
        lines.append(thin)
        lines.append(f"TESTE #{sc['num']:02d}  [{status}]  —  {sc['desc']}")
        lines.append(thin)
        lines.append(f"  Consulta    : {sc['query']}")
        lines.append(f"  Idioma      : {pd.get('language')}")
        lines.append(f"  Intenção    : {pd.get('intent')}")
        lines.append(f"  Estratégia  : {pd.get('retrieval_strategy')}")
        lines.append("")
        lines.append("  SLOTS EXTRAÍDOS:")
        lines.append(f"    place_type              : {slots.get('place_type')}")
        lines.append(f"    sort_preference         : {slots.get('sort_preference')}")
        lines.append(f"    proximity_intent        : {slots.get('proximity_intent_detected')}")
        lines.append(f"    open_now                : {slots.get('open_now')}")
        lines.append(f"    price_max               : {slots.get('price_max')}")
        lines.append(f"    min_rating              : {slots.get('min_rating')}")
        lines.append(f"    min_reviews             : {slots.get('min_reviews')}")
        lines.append(f"    city                    : {slots.get('city')}")
        lines.append(f"    neighborhood            : {slots.get('neighborhood')}")
        lines.append(f"    keywords                : {slots.get('keywords')}")

        cats = slots.get("categories") or []
        lines.append(f"    categories ({len(cats)} total)  : {cats[:8]}{'...' if len(cats) > 8 else ''}")

        debug = pd.get("debug", {})
        if debug.get("detected_signals"):
            lines.append(f"    detected_signals        : {', '.join(debug['detected_signals'])}")

        lines.append("")
        lines.append("  VERIFICAÇÃO DE CATEGORIAS ESPERADAS:")
        if sc["expected_categories"]:
            for cat in sc["expected_categories"]:
                found = cat in r["cat_found"]
                mark = "✓" if found else "✗"
                lines.append(f"    {mark} '{cat}'")
        else:
            lines.append("    (nenhuma categoria específica esperada)")

        lines.append("")
        lines.append("  VERIFICAÇÃO DE FILTROS ESPERADOS:")
        if r["filter_results"]:
            for fk, fv in r["filter_results"].items():
                mark = "✓" if fv["ok"] else "✗"
                lines.append(f"    {mark} {fk}: esperado={fv['expected']!r}  atual={fv['actual']!r}")
        else:
            lines.append("    (nenhum filtro específico esperado além de language=pt-BR)")

    lines.append("")
    lines.append(sep)
    lines.append("RESUMO FINAL")
    lines.append(sep)
    lines.append(f"  Total de testes : {total}")
    lines.append(f"  Passou          : {passed}")
    lines.append(f"  Falhou          : {total - passed}")
    lines.append(f"  Taxa de sucesso : {passed/total*100:.1f}%")
    lines.append("")

    # Per-test summary table
    lines.append("  TABELA DE RESULTADOS:")
    lines.append(f"  {'#':>3}  {'Status':<10}  Descrição")
    lines.append(f"  {'-'*3}  {'-'*10}  {'-'*60}")
    for r in results:
        sc = r["scenario"]
        status = "PASSOU ✓" if r["passed"] else "FALHOU ✗"
        lines.append(f"  {sc['num']:>3}  {status:<10}  {sc['desc']}")

    lines.append(sep)

    content = "\n".join(lines)
    Path(log_path).write_text(content, encoding="utf-8")
    return content


def main():
    print("Inicializando classificador e planner...")
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    planner = QueryPlanner(intent_classifier=classifier)

    print("Executando 30 cenários de teste...")
    results, passed = run_all(planner)

    log_path = Path(__file__).parent / "portuguese_complex_results.log"
    content = write_log(results, passed, log_path)

    print(content)
    print(f"\nLog salvo em: {log_path}")
    print(f"Resultado: {passed}/30 passou")


if __name__ == "__main__":
    main()
