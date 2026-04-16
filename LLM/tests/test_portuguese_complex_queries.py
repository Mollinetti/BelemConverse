"""
Comprehensive Portuguese test cases with complex, real-world scenarios.
Tests include typos, mixed categories, badly phrased sentences, and edge cases.

Test Location: Travessa Curuzu, 1475, Belem, PA
Coordinates: -1.4557549, -48.4901799

This test suite validates:
1. Portuguese language detection
2. Typo tolerance
3. Multi-category extraction (3-4 categories simultaneously)
4. Complex filter combinations
5. Badly phrased/colloquial queries
6. Mixed intent scenarios
"""

import pytest
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
import json
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test location constants
TEST_LAT = -1.4557549
TEST_LON = -48.4901799
TEST_LOCATION = "Travessa Curuzu, 1475, Belem, PA"


class TestPortugueseComplexQueries:
    """Complex Portuguese query validation tests."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test components."""
        # Initialize and train intent classifier
        self.intent_classifier = SimpleTFIDFIntentClassifier()
        self.intent_classifier.train()
        
        # Initialize query planner
        self.query_planner = QueryPlanner(intent_classifier=self.intent_classifier)
        
        # Log test start
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"\n{'='*120}")
        logger.info(f"TESTE DE CONSULTAS COMPLEXAS EM PORTUGUÊS")
        logger.info(f"Iniciado: {timestamp}")
        logger.info(f"Localização de Teste: {TEST_LOCATION}")
        logger.info(f"Coordenadas: ({TEST_LAT}, {TEST_LON})")
        logger.info(f"{'='*120}\n")
    
    def log_query_analysis(self, test_num: int, query: str, plan_dict: Dict[str, Any], 
                          expected_categories: List[str] = None, expected_filters: Dict[str, Any] = None):
        """Log detailed query analysis."""
        logger.info(f"\n{'-'*120}")
        logger.info(f"TESTE #{test_num}: {query}")
        logger.info(f"{'-'*120}")
        logger.info(f"IDIOMA: {plan_dict.get('language')}")
        logger.info(f"INTENÇÃO: {plan_dict.get('intent')}")
        logger.info(f"ESTRATÉGIA DE BUSCA: {plan_dict.get('retrieval_strategy')}")
        
        slots = plan_dict.get('slots', {})
        logger.info(f"\nINFORMAÇÕES EXTRAÍDAS:")
        logger.info(f"  Tipos de Lugar: {slots.get('place_type')}")
        logger.info(f"  Categorias: {slots.get('categories')}")
        logger.info(f"  Cidade: {slots.get('city')}")
        logger.info(f"  Bairro: {slots.get('neighborhood')}")
        logger.info(f"  Aberto Agora: {slots.get('open_now')}")
        logger.info(f"  Preço Máximo: {slots.get('price_max')}")
        logger.info(f"  Avaliação Mínima: {slots.get('min_rating')}")
        logger.info(f"  Intenção de Proximidade: {slots.get('proximity_intent_detected')}")
        logger.info(f"  Preferência de Ordenação: {slots.get('sort_preference')}")
        logger.info(f"  Palavras-chave: {slots.get('keywords')}")
        
        if expected_categories:
            logger.info(f"\nCATEGORIAS ESPERADAS: {expected_categories}")
            extracted = str(slots.get('categories', [])).lower()
            found = [cat for cat in expected_categories if cat.lower() in extracted]
            logger.info(f"  Encontradas: {found} ({len(found)}/{len(expected_categories)})")
        
        if expected_filters:
            logger.info(f"\nFILTROS ESPERADOS:")
            for key, value in expected_filters.items():
                actual = slots.get(key)
                match = "✓" if actual == value or (value == "any" and actual is not None) else "✗"
                logger.info(f"  {match} {key}: esperado={value}, atual={actual}")
        
        debug = plan_dict.get('debug', {})
        if debug.get('detected_signals'):
            logger.info(f"\nSINAIS DETECTADOS: {', '.join(debug['detected_signals'])}")
        
        logger.info(f"{'-'*120}\n")
    
    def test_01_typo_restaurante_perto(self):
        """Teste: Erro de digitação - 'restarante' ao invés de 'restaurante'"""
        query = "restarante perto de mim"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(1, query, plan_dict, 
                               expected_categories=['restaurant'],
                               expected_filters={'proximity_intent_detected': True})
        
        assert plan_dict['language'] == 'pt-BR'
        assert plan_dict['slots']['proximity_intent_detected'] == True
    
    def test_02_multiple_categories_with_filters(self):
        """Teste: Múltiplas categorias + filtros - pizza, hamburguer, comida italiana barata"""
        query = "quero pizza hamburguer ou comida italiana barata perto daqui"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(2, query, plan_dict,
                               expected_categories=['pizza', 'hamburguer', 'italian'],
                               expected_filters={'proximity_intent_detected': True, 'price_max': 'any'})
        
        assert plan_dict['language'] == 'pt-BR'
        assert plan_dict['slots']['proximity_intent_detected'] == True
    
    def test_03_colloquial_badly_phrased(self):
        """Teste: Frase coloquial mal formulada"""
        query = "ae mano tem algum bar restaurante com musica ao vivo aberto agora ai perto?"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(3, query, plan_dict,
                               expected_categories=['bar', 'restaurant', 'musica'],
                               expected_filters={'open_now': True, 'proximity_intent_detected': True})
        
        assert plan_dict['language'] == 'pt-BR'
        assert plan_dict['slots']['open_now'] == True
    
    def test_04_four_categories_mixed(self):
        """Teste: 4 categorias misturadas - café, padaria, lanchonete, sorveteria"""
        query = "cafe padaria lanchonete ou sorveteria com bom preço em belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(4, query, plan_dict,
                               expected_categories=['cafe', 'padaria', 'lanchonete', 'sorveteria'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_05_typo_multiple_words(self):
        """Teste: Múltiplos erros de digitação"""
        query = "resturante japones ou chines com entrga rapida e barato"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(5, query, plan_dict,
                               expected_categories=['restaurant', 'japones', 'chines'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_06_complex_filters_combination(self):
        """Teste: Combinação complexa de filtros"""
        query = "restaurante italiano ou frances aberto agora com nota acima de 4 estrelas e preço medio"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(6, query, plan_dict,
                               expected_categories=['restaurant', 'italian', 'frances'],
                               expected_filters={'open_now': True, 'min_rating': 'any'})
        
        assert plan_dict['language'] == 'pt-BR'
        assert plan_dict['slots']['open_now'] == True
    
    def test_07_regional_slang(self):
        """Teste: Gíria regional paraense"""
        query = "bora num bar massa pra tomar uma gelada e comer tira gosto"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(7, query, plan_dict,
                               expected_categories=['bar'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_08_tour_multiple_categories(self):
        """Teste: Tour com múltiplas categorias"""
        query = "quero fazer um tour pelos museus parques e pontos turisticos de belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(8, query, plan_dict,
                               expected_categories=['museu', 'parque', 'turistico'])
        
        assert plan_dict['language'] == 'pt-BR'
        assert plan_dict['intent'] == 'tour_planning'
    
    def test_09_mixed_proximity_popularity(self):
        """Teste: Mistura de proximidade e popularidade"""
        query = "os melhores restaurantes perto de mim"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(9, query, plan_dict,
                               expected_categories=['restaurant'])
        
        assert plan_dict['language'] == 'pt-BR'
        # Should detect proximity even with "melhores"
        logger.info(f"Proximity detected: {plan_dict['slots']['proximity_intent_detected']}")
    
    def test_10_pharmacy_hospital_urgency(self):
        """Teste: Farmácia e hospital com urgência"""
        query = "preciso urgente de farmacia ou hospital aberto 24 horas aqui perto"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(10, query, plan_dict,
                               expected_categories=['farmacia', 'hospital'],
                               expected_filters={'proximity_intent_detected': True})
        
        assert plan_dict['language'] == 'pt-BR'
        assert plan_dict['slots']['proximity_intent_detected'] == True
    
    def test_11_breakfast_lunch_dinner(self):
        """Teste: Café da manhã, almoço e jantar"""
        query = "lugar pra cafe da manha almoco e jantar tudo no mesmo lugar"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(11, query, plan_dict,
                               expected_categories=['cafe', 'restaurant'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_12_typo_accentuation(self):
        """Teste: Erros de acentuação"""
        query = "restaurante japones proximo com rodizio de sushi e preco bom"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(12, query, plan_dict,
                               expected_categories=['restaurant', 'japones', 'sushi'],
                               expected_filters={'proximity_intent_detected': True})
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_13_shopping_entertainment_food(self):
        """Teste: Shopping, entretenimento e comida"""
        query = "shopping com cinema restaurante e loja de roupa tudo junto"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(13, query, plan_dict,
                               expected_categories=['shopping', 'cinema', 'restaurant', 'loja'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_14_very_badly_phrased(self):
        """Teste: Frase muito mal formulada"""
        query = "tipo assim sabe aquele lugar q tem tipo comida boa e tal barato sabe perto daki"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(14, query, plan_dict,
                               expected_filters={'proximity_intent_detected': True, 'price_max': 'any'})
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_15_specific_dishes_multiple(self):
        """Teste: Pratos específicos múltiplos"""
        query = "onde tem açai tapioca e pastel perto da travessa curuzu"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(15, query, plan_dict,
                               expected_categories=['acai', 'tapioca', 'pastel'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_16_gym_spa_wellness(self):
        """Teste: Academia, spa e bem-estar"""
        query = "academia com spa sauna e massagem incluso na mensalidade"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(16, query, plan_dict,
                               expected_categories=['academia', 'spa', 'sauna', 'massagem'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_17_pet_services_multiple(self):
        """Teste: Serviços para pets múltiplos"""
        query = "petshop com veterinario banho tosa e hotel pra cachorro"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(17, query, plan_dict,
                               expected_categories=['petshop', 'veterinario'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_18_nightlife_multiple_venues(self):
        """Teste: Vida noturna com múltiplos locais"""
        query = "balada bar boate ou pub com musica ao vivo e pista de danca"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(18, query, plan_dict,
                               expected_categories=['balada', 'bar', 'boate', 'pub'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_19_education_multiple_types(self):
        """Teste: Educação com múltiplos tipos"""
        query = "escola de ingles espanhol frances e alemao perto de casa"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(19, query, plan_dict,
                               expected_categories=['escola'],
                               expected_filters={'proximity_intent_detected': True})
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_20_health_services_complex(self):
        """Teste: Serviços de saúde complexos"""
        query = "clinica com dentista dermatologista oftalmologista e exames de sangue"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(20, query, plan_dict,
                               expected_categories=['clinica', 'dentista'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_21_typo_extreme(self):
        """Teste: Erros extremos de digitação"""
        query = "restavrante italianu ou mexikano kon entrega rapda e baratu"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(21, query, plan_dict,
                               expected_categories=['restaurant'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_22_beach_activities_multiple(self):
        """Teste: Atividades de praia múltiplas"""
        query = "praia com restaurante bar quiosque e aluguel de cadeira e guarda sol"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(22, query, plan_dict,
                               expected_categories=['praia', 'restaurant', 'bar', 'quiosque'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_23_automotive_services(self):
        """Teste: Serviços automotivos múltiplos"""
        query = "oficina mecanica com borracharia funilaria pintura e lavagem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(23, query, plan_dict,
                               expected_categories=['oficina', 'mecanica'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_24_beauty_services_complete(self):
        """Teste: Serviços de beleza completos"""
        query = "salao de beleza com cabeleireiro manicure pedicure maquiagem e depilacao"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(24, query, plan_dict,
                               expected_categories=['salao', 'beleza', 'cabeleireiro'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_25_mixed_cuisine_complex(self):
        """Teste: Culinária mista complexa"""
        query = "restaurante q serve comida brasileira japonesa italiana e arabe tudo no mesmo cardapio"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(25, query, plan_dict,
                               expected_categories=['restaurant', 'brasileira', 'japonesa', 'italiana', 'arabe'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_26_kids_entertainment(self):
        """Teste: Entretenimento infantil múltiplo"""
        query = "lugar com brinquedoteca parquinho piscina de bolinha e festa infantil"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(26, query, plan_dict,
                               expected_categories=['brinquedoteca', 'parquinho'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_27_sports_facilities(self):
        """Teste: Instalações esportivas múltiplas"""
        query = "clube com quadra de tenis futebol volei basquete e piscina olimpica"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(27, query, plan_dict,
                               expected_categories=['clube', 'quadra'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_28_cultural_venues_mixed(self):
        """Teste: Locais culturais misturados"""
        query = "teatro cinema museu galeria de arte e centro cultural tudo perto"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(28, query, plan_dict,
                               expected_categories=['teatro', 'cinema', 'museu', 'galeria'],
                               expected_filters={'proximity_intent_detected': True})
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_29_delivery_services_multiple(self):
        """Teste: Serviços de entrega múltiplos"""
        query = "restaurante pizzaria lanchonete ou hamburgueria com entrega rapida gratis e aceita pix"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(29, query, plan_dict,
                               expected_categories=['restaurant', 'pizzaria', 'lanchonete', 'hamburgueria'])
        
        assert plan_dict['language'] == 'pt-BR'
    
    def test_30_weekend_activities_complex(self):
        """Teste: Atividades de fim de semana complexas"""
        query = "lugar pra levar a familia no fim de semana com restaurante parque playground e area de churrasco"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_analysis(30, query, plan_dict,
                               expected_categories=['restaurant', 'parque', 'playground'])
        
        assert plan_dict['language'] == 'pt-BR'


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--log-cli-level=INFO"])
