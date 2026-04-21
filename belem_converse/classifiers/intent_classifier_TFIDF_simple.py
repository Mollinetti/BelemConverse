"""
Simplified TF-IDF Intent Classifier for fast performance.
Optimized for speed while maintaining accuracy.

Includes tour_planning intent for itinerary generation.
"""

import json
import unicodedata
import pickle
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
import numpy as np


# Resolved at import time so train() doesn't pay path-resolution cost.
_IMPLICIT_LEXICON_PATH = (
    Path(__file__).resolve().parent / "data" / "implicit_category_lexicon.json"
)


class SimpleTFIDFIntentClassifier:
    """
    Simplified TF-IDF classifier optimized for speed.
    
    Detects:
    - Intents: location, popularity, price, business_hours, tour_planning, verification
    - Categories: restaurant, cafe, hotel, bar, shopping, entertainment, tourist_attraction, acai
    """

    # Model version - increment when keywords, vectorizer config, or training-data
    # composition change. A version mismatch triggers automatic retraining.
    #
    # Changelog
    # ---------
    # 2.9 — P1 quick wins from docs/spec/12-intent-classifier-improvement-plan.md:
    #       (F5) implicit-category lexicon at
    #            belem_converse/classifiers/data/implicit_category_lexicon.json
    #            now wired into the **category** classifier as additional
    #            training examples. Teaches the classifier semantic phrasings
    #            ("tô com fome" → restaurant, "preciso pernoitar" → hotel)
    #            that contain no category keyword. Runtime Strategy-0 lookup
    #            in QueryPlanner.extract_categories scans the same lexicon.
    #       (F7) bar/shopping/entertainment/ice_cream keyword lexicons
    #            extended (was 7-12 keywords each; now 25-35) so the per-
    #            category training-example count is no longer skewed
    #            relative to restaurant / health / wellness.
    # 2.8 — P0 fixes:
    #       (F1) location-negative examples no longer pollute the category
    #       classifier; only the intent classifier sees them.
    #       (F2) verification intent keyword list trimmed from a 30+ entry
    #       grab-bag to existence-check phrases only — removes the over-fire
    #       on generic question/search words.
    #       (F3) both vectorizers switch to FeatureUnion(word + char_wb (3,5))
    #       to survive PT-BR typos and accent omissions.
    # 2.7 — intent-specific training templates + negative examples for location.
    MODEL_VERSION = "2.9"
    
    def __init__(self):
        # Core intent keywords
        self.intent_keywords = {
            'location': [
                'nearby', 'closest', 'nearest', 'close', 'near', 'around', 'here',
                'próximo', 'próxima', 'proximo', 'proxima', 'perto', 'perto de mim',
                'perto daqui', 'perto daki', 'aqui perto', 'ai perto', 'ali perto',
                'por aqui', 'por perto', 'daqui', 'daki', 'aqui', 'onde', 'localização',
                'where', 'distance', 'walking distance', 'km', 'meters',
                'na minha regiao', 'na minha região', 'na minha area', 'na minha área',
                'perto de casa', 'perto da', 'perto do',
            ],
            'popularity': [
                'best', 'top', 'popular', 'recommended', 'famous', 'good', 'great',
                'melhor', 'popular', 'recomendado', 'bom', 'ótimo', 'excellent',
                'highest rated', 'most reviewed', 'favorite'
            ],
            'price': [
                'cheap', 'affordable', 'budget', 'expensive', 'luxury', 'cost', 'price',
                'barato', 'econômico', 'caro', 'luxo', 'preço', 'inexpensive', 'pricey'
            ],
            'business_hours': [
                'open', 'hours', 'schedule', 'available', 'time', 'when',
                'aberto', 'horário', 'funcionamento', 'disponível', 'closes', 'opens'
            ],
            'tour_planning': [
                'tour', 'itinerary', 'day trip', 'plan my day', 'what to do',
                'roteiro', 'passeio', 'o que fazer', 'dia em', 'planejar',
                'one day', 'um dia', 'half day', 'meio dia', 'schedule my',
                'walking tour', 'food tour', 'sightseeing', 'visit in a day',
                'things to do', 'must see', 'must visit', 'recommend a day',
                'full day', 'morning to evening', 'afternoon tour',
                'suggest places to visit', 'create itinerary', 'trip plan'
            ],
            'verification': [
                # IMPORTANT: keep this list strict. Do NOT add generic
                # question/search words like "find", "looking for", "tem",
                # "where is the", "currently" — they appear in nearly every
                # conversational query and cause this intent to over-fire
                # (see docs/spec/12-intent-classifier-improvement-plan.md F2).
                # Only true existence-verification phrases belong here.
                #
                # Existence checking
                'does exist', 'existe', 'still exists', 'ainda existe',
                # Open/closed status as VERIFICATION (not as business_hours)
                'still open', 'ainda aberto', 'ainda abre', 'ainda funciona',
                'is closed', 'está fechado', 'closed down', 'shut down',
                'fechou', 'encerrou',
                # Verification phrases
                'check if', 'verificar se', 'confirmar se', 'confirm if',
                'make sure', 'certifique', 'verify', 'verificar',
                # Current presence
                'still there', 'still around', 'still operating', 'ainda tem',
                # Rumours / uncertainty
                'heard that', 'ouvi dizer', 'is it true', 'é verdade',
            ]
        }
        
        # Category keywords with tourist_attraction and açaí added
        self.category_keywords = {
            'restaurant': [
                'restaurant', 'restaurante', 'food', 'comida', 'dining', 'eat',
                'pizza', 'sushi', 'italian', 'chinese', 'brazilian', 'japanese',
                'churrascaria', 'barbecue', 'bbq', 'grill', 'steakhouse',
                'bistro', 'lanchonete', 'pizzaria', 'seafood', 'fish',
                'lunch', 'dinner', 'breakfast', 'almoço', 'jantar',
                'typical food', 'comida típica', 'regional food', 'comida regional'
            ],
            'acai': [
                # Primary açaí terms (strict)
                'açaí', 'acai', 'açai', 'acaí', 'assai', 'asai', 'assaí', 'asaí',
                'açaizeiro', 'acaizeiro', 'açaí shop', 'acai shop',
                'açaí place', 'acai place', 'açaí spot', 'acai spot',
                'tomar açaí', 'tomar acai', 'comer açaí', 'comer acai',
                'melhor açaí', 'melhor acai', 'best açaí', 'best acai',
                # Related but açaí-specific
                'açaí na tigela', 'acai bowl', 'açaí bowl', 'tigela de açaí',
                'açaí puro', 'açaí cremoso', 'açaí com banana'
            ],
            'cafe': [
                'cafe', 'cafes', 'café', 'cafés', 'cafeteria', 'coffee', 'coffee shop',
                'latte', 'cappuccino', 'espresso', 'tea', 'tea house',
                'bakery', 'padaria', 'confeitaria', 'dessert', 'sobremesa',
                'pastry', 'doces', 'snack', 'lanche'
            ],
            'ice_cream': [
                # P1/F7: was 7 keywords (42 examples) — under-represented vs
                # restaurant (~168). Topped up with regional + colloquial.
                'ice cream', 'sorvete', 'sorveteria', 'gelato', 'frozen yogurt',
                'picolé', 'picole', 'milkshake', 'sundae', 'casquinha',
                'sorvete artesanal', 'gelato artesanal', 'sorveteria artesanal',
                'sorvete italiano', 'açaí na taça', 'sorbet', 'sorbete',
                'sorvete cremoso', 'sorvete de creme', 'sorvete de chocolate',
                'sundae de chocolate', 'banana split', 'paleta mexicana',
                'gelados', 'sobremesa gelada', 'doce gelado',
            ],
            'hotel': [
                'hotel', 'hotels', 'motel', 'motels', 'accommodation', 'accommodations',
                'stay', 'lodging', 'room', 'rooms', 'suite', 'suites',
                'hospedagem', 'pousada', 'pousadas', 'hostel', 'hostels', 'albergue',
                'sleep', 'overnight', 'place to stay', 'where to stay',
                'inn', 'resort', 'resorts', 'bed and breakfast', 'airbnb'
            ],
            'bar': [
                # P1/F7: was 12 keywords (72 examples). Boosted with regional
                # PT-BR vernacular and beer-domain specifics.
                'bar', 'pub', 'drinks', 'beer', 'cocktail', 'nightlife',
                'bebidas', 'cerveja', 'drink', 'night out', 'club', 'boteco',
                'botequim', 'choperia', 'cervejaria', 'cervejaria artesanal',
                'pub irlandes', 'pub irlandês', 'irish pub', 'sports bar',
                'caipirinha', 'caipirosca', 'gin tonica', 'gim tônica',
                'whisky', 'vinho', 'wine bar', 'wine', 'enoteca',
                'open bar', 'happy hour', 'after work', 'breja', 'tomar uma',
            ],
            'shopping': [
                # P1/F7: was 12 keywords (72 examples). Boosted with retail-
                # vertical terms and PT-BR shopping vernacular.
                'shopping', 'mall', 'store', 'shop', 'buy', 'purchase',
                'loja', 'centro', 'comprar', 'mercado', 'market', 'feira',
                'shopping center', 'centro comercial', 'galeria comercial',
                'lojinhas', 'comércio', 'comercio', 'outlet', 'butique',
                'butique de roupa', 'loja de roupa', 'loja de sapato',
                'loja de bolsa', 'loja de acessórios', 'loja de acessorios',
                'loja de presente', 'loja de souvenir', 'loja de eletronicos',
                'departamento', 'centro de compras', 'shopping mall',
            ],
            'entertainment': [
                # P1/F7: was 9 keywords (54 examples). Boosted with
                # cinema-domain + cultural-event vocabulary.
                'entertainment', 'cinema', 'theater', 'fun', 'activity',
                'entretenimento', 'diversão', 'diversao', 'teatro', 'movie',
                'show', 'sala de cinema', 'cinemas', 'multiplex',
                'peça de teatro', 'peca de teatro', 'pecas teatrais',
                'shows musicais', 'apresentação', 'apresentacao', 'concerto',
                'evento cultural', 'eventos culturais', 'standup', 'stand up',
                'comédia', 'comedia', 'circo', 'espetáculo', 'espetaculo',
            ],
            'health': [
                'clinica', 'clínica', 'hospital', 'farmacia', 'farmácia', 'drogaria',
                'dentista', 'dentista', 'odontologico', 'odontológico', 'odontologia',
                'medico', 'médico', 'medica', 'médica', 'consulta', 'consultar',
                'dermatologista', 'oftalmologista', 'ortopedista', 'cardiologista',
                'pediatra', 'ginecologista', 'urologista', 'neurologista',
                'exame', 'exames', 'laboratorio', 'laboratório', 'analise', 'análise',
                'ubs', 'upa', 'pronto socorro', 'pronto-socorro', 'emergencia', 'emergência',
                'saude', 'saúde', 'health', 'medical', 'clinic', 'pharmacy', 'drugstore',
                'doctor', 'dentist', 'hospital', 'urgent care', 'blood test'
            ],
            'beauty': [
                'salao', 'salão', 'salao de beleza', 'salão de beleza', 'beauty salon',
                'cabeleireiro', 'cabeleireira', 'cabelereiro', 'hair salon', 'hairdresser',
                'manicure', 'pedicure', 'manicura', 'unhas', 'nail salon', 'nail',
                'maquiagem', 'maquiar', 'makeup', 'make up', 'make-up',
                'depilacao', 'depilação', 'depilacao a laser', 'waxing', 'laser hair removal',
                'estetica', 'estética', 'esteticista', 'aesthetics', 'facial', 'limpeza de pele',
                'barbearia', 'barbeiro', 'barber', 'barber shop', 'barbershop',
                'sobrancelha', 'design de sobrancelha', 'eyebrow', 'micropigmentacao',
                'spa facial', 'tratamento de pele', 'skin care', 'skincare'
            ],
            'automotive': [
                'oficina', 'mecanica', 'mecânica', 'mecanico', 'mecânico', 'auto repair',
                'borracharia', 'borracha', 'pneu', 'pneus', 'tire', 'tires',
                'funilaria', 'funileiro', 'body shop', 'lataria',
                'pintura automotiva', 'pintura de carro', 'auto paint',
                'lavagem', 'lava jato', 'lava-jato', 'car wash', 'lavagem de carro',
                'auto center', 'autocenter', 'centro automotivo',
                'concessionaria', 'concessionária', 'dealership', 'car dealer',
                'troca de oleo', 'troca de óleo', 'oil change', 'revisao', 'revisão',
                'alinhamento', 'balanceamento', 'alignment', 'balancing',
                'eletrica automotiva', 'elétrica automotiva', 'auto electric',
                'guincho', 'reboque', 'tow truck', 'socorro mecanico'
            ],
            'wellness': [
                'academia', 'gym', 'ginasio', 'ginásio', 'fitness', 'fitness center',
                'spa', 'spa day', 'day spa',
                'sauna', 'sauna seca', 'sauna umida', 'sauna úmida',
                'massagem', 'massagista', 'massage', 'massage therapy',
                'pilates', 'studio de pilates', 'pilates studio',
                'yoga', 'studio de yoga', 'yoga studio', 'meditacao', 'meditação',
                'crossfit', 'box de crossfit', 'crossfit box',
                'musculacao', 'musculação', 'weight training', 'personal trainer',
                'hidroginastica', 'hidroginástica', 'aqua aerobics',
                'fisioterapia', 'fisioterapeuta', 'physiotherapy', 'physical therapy',
                'bem estar', 'bem-estar', 'wellness', 'relaxamento', 'relaxation',
                'acupuntura', 'acupuncture', 'quiropraxia', 'chiropractic'
            ],
            'pets': [
                'petshop', 'pet shop', 'pet store', 'loja de animais',
                'veterinario', 'veterinária', 'veterinário', 'vet', 'veterinary',
                'clinica veterinaria', 'clínica veterinária', 'animal clinic',
                'banho', 'tosa', 'banho e tosa', 'grooming', 'pet grooming',
                'hotel para cachorro', 'hotel para animais', 'pet hotel', 'canil',
                'adestramento', 'adestrador', 'dog training', 'dog trainer',
                'cachorro', 'gato', 'animal', 'pet', 'dog', 'cat',
                'racao', 'ração', 'pet food', 'acessorios para pets'
            ],
            'nightlife': [
                'balada', 'boate', 'night club', 'nightclub', 'clube noturno',
                'show', 'show ao vivo', 'live show', 'live music', 'musica ao vivo',
                'pista de danca', 'pista de dança', 'dance floor',
                'festa', 'festas', 'party', 'parties',
                'happy hour', 'after work',
                'karaoke', 'karaokê', 'karaoke bar',
                'lounge', 'rooftop bar', 'rooftop',
                'open bar', 'barzinho', 'botequim'
            ],
            'kids': [
                'brinquedoteca', 'brinquedos', 'toy store', 'toy',
                'parquinho', 'playground', 'play area', 'area de lazer infantil',
                'piscina de bolinha', 'ball pit',
                'festa infantil', 'buffet infantil', 'kids party', 'birthday party',
                'escola de futebol', 'escola de natacao', 'escola de natação',
                'escolinha', 'aula para criancas', 'aula para crianças',
                'crianca', 'criança', 'criancas', 'crianças', 'kids', 'children',
                'infantil', 'bebe', 'bebê', 'baby', 'toddler',
                'parque infantil', 'kids park', 'family park'
            ],
            'sports': [
                'quadra', 'quadra de tenis', 'quadra de tênis', 'tennis court',
                'quadra de futebol', 'campo de futebol', 'soccer field', 'football field',
                'quadra de volei', 'quadra de vôlei', 'volleyball court',
                'quadra de basquete', 'basketball court',
                'piscina', 'piscina olimpica', 'piscina olímpica', 'swimming pool',
                'clube', 'clube esportivo', 'sports club', 'athletic club',
                'futebol', 'soccer', 'football', 'tenis', 'tênis', 'tennis',
                'volei', 'vôlei', 'volleyball', 'basquete', 'basketball',
                'natacao', 'natação', 'swimming', 'corrida', 'running',
                'ciclismo', 'cycling', 'bike', 'bicicleta',
                'arena', 'estadio', 'estádio', 'stadium', 'ginasio esportivo'
            ],
            'tourist_attraction': [
                # General tourist terms
                'tourist attraction', 'tourist spot', 'atração turística', 'ponto turístico',
                'tourism', 'turismo', 'sightseeing', 'tourist', 'turista', 'visit', 'visitar',
                'conhecer', 'explore', 'explorar', 'landmark', 'marco histórico',
                # Museums
                'museum', 'museu', 'museums', 'museus', 'gallery', 'galeria', 'exhibition', 'exposição',
                # Parks and nature
                'park', 'parque', 'parks', 'parques', 'garden', 'jardim', 'botanical', 'botânico',
                'nature reserve', 'reserva natural', 'ecological', 'ecológico', 'zoo', 'zoológico',
                # Historical sites
                'historical site', 'sítio histórico', 'historic', 'histórico', 'history', 'história',
                'ruins', 'ruínas', 'archaeological', 'arqueológico', 'old town', 'cidade velha',
                'heritage', 'patrimônio', 'colonial', 'antigo', 'ancient', 'century', 'século',
                # Religious sites
                'church', 'igreja', 'churches', 'igrejas', 'cathedral', 'catedral', 'basilica', 'basílica',
                'chapel', 'capela', 'temple', 'templo', 'monastery', 'mosteiro', 'convent', 'convento',
                # Monuments and sculptures
                'monument', 'monumento', 'monuments', 'monumentos', 'statue', 'estátua', 'memorial',
                'sculpture', 'escultura', 'obelisk', 'obelisco',
                # Plazas and squares
                'plaza', 'praça', 'square', 'town square', 'largo', 'terreiro',
                # Fortresses and military
                'fortress', 'fortaleza', 'fort', 'forte', 'castle', 'castelo', 'citadel', 'cidadela',
                'military', 'militar', 'barracks', 'quartel',
                # Beaches and waterfront
                'beach', 'praia', 'beaches', 'praias', 'waterfront', 'orla', 'pier', 'píer',
                'dock', 'doca', 'port', 'porto', 'bay', 'baía', 'river', 'rio', 'ilha', 'island',
                # Theaters and cultural venues
                'theater', 'teatro', 'opera house', 'casa de ópera', 'cultural center', 'centro cultural',
                'arts center', 'centro de artes', 'auditorium', 'auditório',
                # Markets (as tourist spots)
                'ver-o-peso', 'mercado ver o peso', 'traditional market', 'mercado tradicional',
                # General attraction words
                'attraction', 'atração', 'attractions', 'atrações', 'things to see', 'o que ver',
                'must see', 'imperdível', 'famous place', 'lugar famoso', 'iconic', 'icônico'
            ]
        }
        
        # Vectorizers: word features for canonical phrasing, char_wb features
        # for typo / accent-omission robustness (P0/F3 in the improvement plan).
        # FeatureUnion concatenates the two sparse matrices. Latency impact is
        # negligible (<1 ms) thanks to capped max_features.
        self.intent_vectorizer = FeatureUnion([
            ("word", TfidfVectorizer(
                analyzer="word", ngram_range=(1, 2), max_features=500, lowercase=True,
            )),
            ("char", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), max_features=1000, lowercase=True,
            )),
        ])

        self.category_vectorizer = FeatureUnion([
            ("word", TfidfVectorizer(
                analyzer="word", ngram_range=(1, 2), max_features=800, lowercase=True,
            )),
            ("char", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), max_features=1500, lowercase=True,
            )),
        ])
        
        # Simple, fast classifiers
        self.intent_classifier = LogisticRegression(
            random_state=42, 
            max_iter=500, 
            class_weight='balanced'
        )
        
        self.category_classifier = LogisticRegression(
            random_state=42, 
            max_iter=500, 
            class_weight='balanced'
        )
        
        self.is_trained = False
        self.model_dir = Path(__file__).parent / "models"
        self.model_dir.mkdir(exist_ok=True)
    
    def normalize(self, text: str) -> str:
        """Quick text normalization."""
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()
    
    def _load_implicit_lexicon(self) -> Dict[str, List[str]]:
        """Load and flatten the implicit-category lexicon for training-data
        injection (P1/F5).

        Returns a flat ``{category: [phrases]}`` dict where phrases from all
        languages are concatenated under the same category key. Phrase order
        is PT-first then EN — matters only for log readability since training
        order doesn't affect logistic regression with class_weight='balanced'.

        On missing or malformed file we return an empty dict and log a warning;
        training still proceeds without the lexicon (the classifier falls back
        to its regular keyword-templated examples). This MUST be permissive:
        the classifier needs to remain trainable on machines that don't have
        the data file shipped (e.g. minimal Docker images).
        """
        try:
            with open(_IMPLICIT_LEXICON_PATH, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            print(
                f"WARNING: implicit lexicon missing at {_IMPLICIT_LEXICON_PATH} "
                f"— training without semantic examples (F5)."
            )
            return {}
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARNING: failed to load implicit lexicon: {e} — training without F5.")
            return {}

        flat: Dict[str, List[str]] = {}
        for lang_key, categories in raw.items():
            if lang_key.startswith("_") or not isinstance(categories, dict):
                continue
            for category, phrases in categories.items():
                if not isinstance(phrases, list):
                    continue
                flat.setdefault(category, []).extend(
                    p for p in phrases if isinstance(p, str)
                )
        return flat

    def _prepare_simple_training_data(
        self,
        keywords_dict: Dict[str, List[str]],
        include_location_negatives: bool = True,
        semantic_examples: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Prepare training data with intent-specific templates and negative examples.

        Root cause of previous false positives: the generic template "find {keyword}"
        was applied to ALL intents, so the TF-IDF learned that "find" + any word
        correlates with location intent.  Fix:
        1. Use intent-specific sentence templates so each intent has distinct phrasing.
        2. Add explicit negative examples for location (sentences that contain category
           keywords but NO proximity signal) so the classifier learns to distinguish
           "I want a manicure" from "I want a manicure near me".

        ``include_location_negatives`` MUST be ``False`` when this function is
        called for the **category** classifier — those negatives are labeled
        ``'popularity'``, which is a valid intent label but NOT a category.
        Including them in category training poisoned the model with a phantom
        ``popularity`` category in v2.7 (see plan F1). Flag exists so the same
        helper still serves both training paths cleanly.

        ``semantic_examples`` (P1/F5) is an optional ``{label: [phrases]}``
        dict appended verbatim (after normalisation) to the training set.
        Used to inject the implicit-category lexicon into the **category**
        classifier so phrases like "tô com fome" learn to score the
        ``restaurant`` class without needing a category keyword. Phrases here
        are added with NO templating — they're already complete user-style
        utterances.
        """
        # Intent-specific templates — each intent gets phrasing that is natural for it
        intent_templates = {
            'location': [
                '{kw} near me',
                '{kw} nearby',
                '{kw} close to me',
                '{kw} around here',
                '{kw} perto de mim',
                '{kw} perto daqui',
                '{kw} aqui perto',
                'find {kw} nearby',
                'closest {kw}',
                '{kw} proximo',
            ],
            'popularity': [
                'best {kw}',
                'top {kw}',
                'most popular {kw}',
                'highly rated {kw}',
                'recommended {kw}',
                'melhor {kw}',
                '{kw} mais popular',
                '{kw} bem avaliado',
                'famous {kw}',
                '{kw} otimo',
            ],
            'price': [
                'cheap {kw}',
                'affordable {kw}',
                'budget {kw}',
                '{kw} barato',
                '{kw} economico',
                '{kw} em conta',
                'inexpensive {kw}',
                '{kw} preco baixo',
                'low cost {kw}',
                '{kw} acessivel',
            ],
            'business_hours': [
                '{kw} open now',
                '{kw} aberto agora',
                'is {kw} open',
                '{kw} open 24 hours',
                '{kw} aberto 24 horas',
                '{kw} horario de funcionamento',
                'when does {kw} open',
                '{kw} ainda aberto',
                '{kw} funcionando agora',
                'what time does {kw} close',
            ],
            'tour_planning': [
                'tour of {kw}',
                'itinerary for {kw}',
                'day trip to {kw}',
                'plan a visit to {kw}',
                'roteiro de {kw}',
                'passeio por {kw}',
                'o que fazer em {kw}',
                'visit {kw} in one day',
                'sightseeing {kw}',
                'full day at {kw}',
            ],
            'verification': [
                'does {kw} exist',
                'is {kw} still open',
                '{kw} ainda existe',
                'is there a {kw}',
                'tem {kw}',
                'verificar {kw}',
                'confirmar {kw}',
                'check if {kw} is open',
                '{kw} ainda funciona',
                'is {kw} still there',
            ],
        }

        # Default templates for any intent not listed above
        default_templates = [
            '{kw}',
            'find {kw}',
            'show me {kw}',
            'I need {kw}',
            'looking for {kw}',
        ]

        X: List[str] = []
        y: List[str] = []

        for label, keywords in keywords_dict.items():
            templates = intent_templates.get(label, default_templates)
            for keyword in keywords:
                kw_norm = self.normalize(keyword)
                # Add raw keyword
                X.append(kw_norm)
                y.append(label)
                # Add templated variations
                for tmpl in templates:
                    X.append(self.normalize(tmpl.format(kw=keyword)))
                    y.append(label)

        # --- Semantic examples (P1/F5) ---
        # Appended BEFORE the location_negatives block so the early-return for
        # category training still picks them up. Phrases are user-style
        # utterances with NO category keyword by design — they teach the
        # classifier semantic-to-category mappings the keyword lexicon
        # cannot reasonably enumerate.
        if semantic_examples:
            for label, phrases in semantic_examples.items():
                for phrase in phrases:
                    X.append(self.normalize(phrase))
                    y.append(label)

        # --- Negative examples for location intent (P0/F1: intent-only) ---
        # These are realistic non-proximity queries that should NOT trigger
        # location intent. They contain category-domain words that were causing
        # false positives. They are LABELED 'popularity' as a neutral catch
        # bucket — see _prepare_simple_training_data docstring on why this
        # MUST NOT leak into the category classifier.
        if not include_location_negatives:
            return X, y

        location_negatives = [
            # beauty
            'salao de beleza com cabeleireiro manicure pedicure',
            'quero fazer manicure e pedicure',
            'preciso cortar o cabelo no cabeleireiro',
            'agendar depilacao no salao',
            'maquiagem para festa no salao',
            # wellness
            'academia com spa sauna e massagem',
            'quero fazer massagem relaxante',
            'aula de pilates e yoga',
            'personal trainer na academia',
            'crossfit e musculacao',
            # health
            'clinica com dentista e dermatologista',
            'consulta medica no hospital',
            'exames de sangue no laboratorio',
            'farmacia com remedios',
            'ubs e pronto socorro',
            # kids
            'brinquedoteca com parquinho e piscina de bolinha',
            'festa infantil com buffet',
            'escola de natacao para criancas',
            # sports
            'clube com quadra de tenis e piscina olimpica',
            'campo de futebol e quadra de volei',
            'natacao e ciclismo no clube',
            # nightlife
            'balada com musica ao vivo e pista de danca',
            'bar e boate com open bar',
            'show ao vivo no karaoke',
            # shopping / entertainment
            'shopping com cinema e loja de roupa',
            'teatro e museu no centro cultural',
            'galeria de arte e exposicao',
            # food (no proximity)
            'restaurante italiano com cardapio variado',
            'pizza e hamburguer com entrega',
            'cafe da manha almoco e jantar no mesmo lugar',
            # automotive
            'oficina mecanica com borracharia e funilaria',
            'lava jato e troca de oleo',
            # pets
            'petshop com veterinario banho e tosa',
            'hotel para cachorro e adestramento',
        ]
        for neg in location_negatives:
            X.append(self.normalize(neg))
            y.append('popularity')  # assign to a neutral intent, not location

        return X, y
    
    def _get_model_file(self) -> Path:
        """Get versioned model file path."""
        return self.model_dir / f"simple_tfidf_models_v{self.MODEL_VERSION}.pkl"
    
    def train(self):
        """Train both classifiers quickly."""
        try:
            # Try to load pre-trained models
            if self._load_models():
                return
            
            # Train intent classifier — location_negatives are appropriate
            # here because 'popularity' is a valid intent label.
            # No semantic_examples: the implicit-category lexicon carries
            # category labels, not intent labels, so it has nothing useful
            # to say about the intent classifier.
            X_intent, y_intent = self._prepare_simple_training_data(
                self.intent_keywords, include_location_negatives=True,
            )
            X_intent_vec = self.intent_vectorizer.fit_transform(X_intent)
            self.intent_classifier.fit(X_intent_vec, y_intent)

            # Train category classifier — location_negatives MUST be excluded
            # because 'popularity' is NOT a category. Including them in v2.7
            # caused a phantom 'popularity' category with 26 false positives
            # on the diagnostic corpus (plan F1).
            #
            # P1/F5: inject the implicit-category lexicon as additional
            # training examples so the classifier learns colloquial framings
            # ("tô com fome", "preciso pernoitar", "quero relaxar") that
            # contain no category keyword. Lexicon source:
            # belem_converse/classifiers/data/implicit_category_lexicon.json
            implicit_examples = self._load_implicit_lexicon()
            if implicit_examples:
                total_phrases = sum(len(v) for v in implicit_examples.values())
                print(
                    f"  -> P1/F5: injecting {total_phrases} implicit-category "
                    f"phrases across {len(implicit_examples)} categories"
                )
            X_category, y_category = self._prepare_simple_training_data(
                self.category_keywords,
                include_location_negatives=False,
                semantic_examples=implicit_examples,
            )
            X_category_vec = self.category_vectorizer.fit_transform(X_category)
            self.category_classifier.fit(X_category_vec, y_category)
            
            self.is_trained = True
            
            # Save models for next time
            self._save_models()
            
        except Exception as e:
            print(f"Training error: {e}")
            self.is_trained = False
    
    def _save_models(self):
        """Save trained models to disk."""
        try:
            model_data = {
                'intent_vectorizer': self.intent_vectorizer,
                'intent_classifier': self.intent_classifier,
                'category_vectorizer': self.category_vectorizer,
                'category_classifier': self.category_classifier,
                'version': self.MODEL_VERSION
            }
            
            model_file = self._get_model_file()
            with open(model_file, 'wb') as f:
                pickle.dump(model_data, f)
                
        except Exception as e:
            print(f"Model save error: {e}")
    
    def _load_models(self) -> bool:
        """Load pre-trained models from disk."""
        try:
            model_file = self._get_model_file()
            
            if not model_file.exists():
                return False
                
            with open(model_file, 'rb') as f:
                model_data = pickle.load(f)
            
            # Check version
            if model_data.get('version') != self.MODEL_VERSION:
                return False
            
            self.intent_vectorizer = model_data['intent_vectorizer']
            self.intent_classifier = model_data['intent_classifier']
            self.category_vectorizer = model_data['category_vectorizer']
            self.category_classifier = model_data['category_classifier']
            
            self.is_trained = True
            return True
            
        except Exception as e:
            print(f"Model load error: {e}")
            return False
    
    def predict_intent(self, query: str) -> Dict[str, Any]:
        """Fast intent prediction."""
        if not self.is_trained:
            self.train()
        
        if not self.is_trained:
            return {
                'intents': [{'intent': 'unknown', 'confidence': 0.0}],
                'primary_intent': 'unknown',
                'primary_confidence': 0.0
            }
        
        query_norm = self.normalize(query)
        X_vec = self.intent_vectorizer.transform([query_norm])
        proba = self.intent_classifier.predict_proba(X_vec)[0]
        
        # Get probabilities
        intent_probs = dict(zip(self.intent_classifier.classes_, proba))
        
        # Sort by confidence
        sorted_intents = sorted(intent_probs.items(), key=lambda x: x[1], reverse=True)
        
        # Return top results
        top_intents = []
        for intent, confidence in sorted_intents[:3]:
            if confidence >= 0.2:
                top_intents.append({
                    'intent': intent,
                    'confidence': float(confidence)
                })
        
        if not top_intents:
            return {
                'intents': [{'intent': 'unknown', 'confidence': 0.0}],
                'primary_intent': 'unknown',
                'primary_confidence': 0.0
            }
        
        return {
            'intents': top_intents,
            'primary_intent': top_intents[0]['intent'],
            'primary_confidence': top_intents[0]['confidence']
        }
    
    def predict_category(self, query: str) -> Dict[str, Any]:
        """Fast category prediction."""
        if not self.is_trained:
            self.train()
        
        if not self.is_trained:
            return {
                'categories': [{'category': 'restaurant', 'confidence': 0.5}],
                'primary_category': 'restaurant',
                'primary_confidence': 0.5
            }
        
        query_norm = self.normalize(query)
        X_vec = self.category_vectorizer.transform([query_norm])
        proba = self.category_classifier.predict_proba(X_vec)[0]
        
        # Get probabilities
        category_probs = dict(zip(self.category_classifier.classes_, proba))
        
        # Sort by confidence
        sorted_categories = sorted(category_probs.items(), key=lambda x: x[1], reverse=True)
        
        # Return top results
        top_categories = []
        for category, confidence in sorted_categories[:3]:
            if confidence >= 0.2:
                top_categories.append({
                    'category': category,
                    'confidence': float(confidence)
                })
        
        if not top_categories:
            return {
                'categories': [{'category': 'restaurant', 'confidence': 0.5}],
                'primary_category': 'restaurant',
                'primary_confidence': 0.5
            }
        
        return {
            'categories': top_categories,
            'primary_category': top_categories[0]['category'],
            'primary_confidence': top_categories[0]['confidence']
        }
    
    def predict(self, query: str) -> Dict[str, Any]:
        """Fast prediction of both intent and category."""
        intent_result = self.predict_intent(query)
        category_result = self.predict_category(query)
        
        return {
            'intents': intent_result['intents'],
            'primary_intent': intent_result['primary_intent'],
            'primary_intent_confidence': intent_result['primary_confidence'],
            'categories': category_result['categories'],
            'primary_category': category_result['primary_category'],
            'primary_category_confidence': category_result['primary_confidence'],
            'original_query': query
        }
    
    def is_tour_planning_query(self, query: str) -> bool:
        """Quick check if query is asking for tour planning."""
        result = self.predict_intent(query)
        
        # Check classifier result
        if result.get('primary_intent') == 'tour_planning':
            return True
        
        # Fallback to keyword detection
        query_lower = query.lower()
        tour_keywords = [
            'tour', 'itinerary', 'day trip', 'plan my day',
            'roteiro', 'passeio', 'o que fazer', 'dia em'
        ]
        
        return any(keyword in query_lower for keyword in tour_keywords)
    
    def force_retrain(self):
        """Force retraining of models (useful when keywords are updated)."""
        # Delete existing model file
        model_file = self._get_model_file()
        if model_file.exists():
            model_file.unlink()
        
        self.is_trained = False
        self.train()
