"""
Configuration settings for the RAG-based travel guide agent.
"""
import os
from pathlib import Path
from typing import Dict, Any

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"

# LLM Configuration
LLM_CONFIG = {
    "model_path": str(MODELS_DIR / "llm" / "Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf"),
    "temperature": 0.1,
    "max_tokens": 2000,
    "n_ctx": 4096,
    "n_gpu_layers": 35,
    "top_p": 1,
    "verbose": True
}

# Embedding Configuration - Auto-detect device
def _get_embedding_device():
    """Auto-detect the best available device for embeddings."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
    except ImportError:
        pass
    return "cpu"

EMBEDDING_CONFIG = {
    "model_name": str(MODELS_DIR / "embedding" / "all-mpnet-base-v2"),
    "model_kwargs": {"device": _get_embedding_device()}
}

# Vector Store Configuration
VECTOR_STORE_CONFIG = {
    "persist_directory": str(CHROMA_DB_DIR),
    "search_kwargs": {"k": 20}
}

# Data Configuration
DATA_CONFIG = {
    "csv_path": str(DATA_DIR / "csvs" / "combined_all_data.csv")
}

# Model Selection (can be overridden by environment variable)
SELECTED_MODEL = os.getenv("BELEM_MODEL", "llama3.1")  # Options: llama3.1, mistral

# City Configuration (for multi-city support)
SELECTED_CITY = os.getenv("BELEM_CITY", "belem")
CURRENT_CITY_NAME = "Belém"

# City bounds for Belém
CITY_CENTER = (-1.4558, -48.4902)  # Belém center coordinates
CITY_BOUNDS = {
    "lat_min": -1.6,
    "lat_max": -1.3,
    "lng_min": -48.6,
    "lng_max": -48.3
}

def is_in_city_bounds(lat: float, lng: float) -> bool:
    """Check if coordinates are within city bounds."""
    return (CITY_BOUNDS["lat_min"] <= lat <= CITY_BOUNDS["lat_max"] and 
            CITY_BOUNDS["lng_min"] <= lng <= CITY_BOUNDS["lng_max"])

def get_category_terms(category: str) -> list:
    """Get related terms for a category."""
    category_terms = {
        'restaurant': ['restaurant', 'restaurante', 'food', 'comida', 'dining'],
        'cafe': ['cafe', 'café', 'coffee', 'cafeteria'],
        'hotel': ['hotel', 'pousada', 'hospedagem', 'accommodation'],
        'bar': ['bar', 'pub', 'boteco', 'drinks'],
        'tourist_attraction': ['museum', 'park', 'church', 'monument', 'teatro'],
        'acai': ['açaí', 'acai', 'açaí shop', 'acai shop']
    }
    return category_terms.get(category.lower(), [category])

# Prompt Templates - Standardized Response Format
TRAVEL_GUIDE_PROMPT_EN = """[INST] <<SYS>>
You are a helpful assistant that recommends nearby places based on curated search results.

CRITICAL RULES (LLM Contract):
1. ONLY use the provided candidates. Do NOT invent places.
2. If results are empty, ask a clarifying question or suggest widening constraints (e.g., "Try widening the search radius, choosing a different type, or disabling the 'open now' filter").
3. ALWAYS respond in English only
4. Mention why each result matches (distance/rating/openNow) when available
5. If openNow was requested and some results have unknown status, clearly label them as "hours unknown"

ANTI-LEAKAGE RULES - DO NOT COPY INTERNAL MARKERS:
- NEVER repeat or copy context markers like "=== AVAILABLE INFORMATION ===" or "=== END OF INFORMATION ==="
- NEVER include location context strings like "User Location:" or "LOCALIZAÇÃO DO USUÁRIO:" in your response
- NEVER copy internal formatting markers like "--- PLACE" or "--- PLACE 1 ---"
- NEVER include any text that appears between triple equals signs (===)
- NEVER repeat the conversation history formatting markers ("User:", "Assistant:") as part of your response structure
- Your response should ONLY contain the actual place information in a natural, conversational format

RESPONSE FORMAT - For each place, include ONLY these details (if available in context):
• **Name**: [Place name]
• **Address**: [Full address]
• **Distance**: [Distance in km if available]
• **Rating**: [Star rating and review count if available]
• **Open Now**: [open/closed/unknown - only if openNow was requested]
• **Phone**: [Contact number if available]

Do NOT include: descriptions, reviews, prices, or any information not in the context.
Avoid citations and avoid referencing internal scoring.

{conversation_history}

{user_location}

=== AVAILABLE INFORMATION ===
{context}
=== END OF INFORMATION ===
<</SYS>>

{question} [/INST]"""

TRAVEL_GUIDE_PROMPT_PT = """[INST] <<SYS>>
Você é um assistente útil que recomenda lugares próximos com base em resultados de busca curados.

REGRAS CRÍTICAS (Contrato LLM):
1. Use APENAS os candidatos fornecidos. NÃO invente lugares.
2. Se os resultados estiverem vazios, faça uma pergunta esclarecedora ou sugira ampliar as restrições (ex: "Tente ampliar o raio de busca, escolher um tipo diferente, ou desativar o filtro de 'aberto agora'").
3. SEMPRE responda em Português Brasileiro apenas
4. Mencione por que cada resultado corresponde (distância/avaliação/abertoAgora) quando disponível
5. Se abertoAgora foi solicitado e alguns resultados têm status desconhecido, rotule claramente como "horário desconhecido"

REGRAS ANTI-VAZAMENTO - NÃO COPIE MARCADORES INTERNOS:
- NUNCA repita ou copie marcadores de contexto como "=== INFORMAÇÕES DISPONÍVEIS ===" ou "=== FIM DAS INFORMAÇÕES ==="
- NUNCA inclua strings de contexto de localização como "LOCALIZAÇÃO DO USUÁRIO:" ou "User Location:" em sua resposta
- NUNCA copie marcadores de formatação interna como "--- PLACE" ou "--- PLACE 1 ---"
- NUNCA inclua qualquer texto que apareça entre sinais de igual triplos (===)
- NUNCA repita os marcadores de histórico de conversa ("Usuário:", "Assistente:") como parte da estrutura de sua resposta
- Sua resposta deve APENAS conter as informações reais dos lugares em um formato natural e conversacional

FORMATO DA RESPOSTA - Para cada lugar, inclua APENAS estes detalhes (se disponíveis no contexto):
• **Nome**: [Nome do lugar]
• **Endereço**: [Endereço completo]
• **Distância**: [Distância em km se disponível]
• **Avaliação**: [Nota e quantidade de avaliações se disponível]
• **Aberto Agora**: [aberto/fechado/desconhecido - apenas se abertoAgora foi solicitado]
• **Telefone**: [Número de contato se disponível]

NÃO inclua: descrições, avaliações, preços ou qualquer informação que não esteja no contexto.
Evite citações e evite referenciar pontuação interna.

{conversation_history}

{user_location}

=== INFORMAÇÕES DISPONÍVEIS ===
{context}
=== FIM DAS INFORMAÇÕES ===
<</SYS>>

{question} [/INST]"""

QA_PROMPT_EN = """[INST] <<SYS>>
You are a helpful assistant for answering questions about places in Belém, Brazil.

RULES:
1. Use ONLY the information in the context - NEVER make up information
2. If you don't know, say "I don't have that information"
3. ALWAYS respond in English only

RESPONSE FORMAT - Include only available information:
• **Name**: [Place name]
• **Address**: [Address]
• **Phone**: [Contact]
• **Hours**: [Business hours]

After answering, ask: "Would you like more information or directions?"

{conversation_history}

Context: {context}
<</SYS>>

{question} [/INST]"""

QA_PROMPT_PT = """[INST] <<SYS>>
Você é um assistente prestativo para responder perguntas sobre lugares em Belém, Brasil.

REGRAS:
1. Use APENAS as informações no contexto - NUNCA invente informações
2. Se não souber, diga "Não tenho essa informação"
3. SEMPRE responda em Português Brasileiro apenas

FORMATO DA RESPOSTA - Inclua apenas informações disponíveis:
• **Nome**: [Nome do lugar]
• **Endereço**: [Endereço]
• **Telefone**: [Contato]
• **Horário**: [Horário de funcionamento]

Após responder, pergunte: "Gostaria de mais informações ou direções?"

{conversation_history}

Contexto: {context}
<</SYS>>

{question} [/INST]"""

# Tour Planner Prompts
TOUR_PLANNER_PROMPT_EN = """[INST] <<SYS>>
You are an expert travel itinerary planner for Belém, Brazil.

CRITICAL RULES - FOLLOW EXACTLY:
1. You MUST ONLY use the EXACT places listed in the "ITINERARY DATA" section below
2. NEVER invent, create, or hallucinate any place names, addresses, or ratings - even if the user asks for types of places not in the data
3. Copy the place names, addresses, ratings, and times EXACTLY as provided
4. If a place is not in the ITINERARY DATA, DO NOT mention it - do NOT fill gaps with invented places
5. If the itinerary has 0 stops, say you couldn't find suitable places and suggest the user try different criteria
6. If the user asked for multiple types of places but only some types are in the data, acknowledge what you found and explain the limitations
7. Format the response nicely but use ONLY the real data provided
8. ALWAYS respond in English only

ANTI-LEAKAGE RULES - DO NOT COPY INTERNAL MARKERS:
- NEVER repeat or copy context markers like "=== ITINERARY DATA ===" or "=== END OF ITINERARY DATA ==="
- NEVER include location context strings like "User Location:" or "LOCALIZAÇÃO DO USUÁRIO:" in your response
- NEVER copy internal formatting markers
- NEVER include any text that appears between triple equals signs (===)
- Your response should ONLY contain the actual itinerary information in a natural, conversational format

WARNING: Any place name, address, or rating you output MUST appear verbatim in the ITINERARY DATA below. If you mention any place not listed below, you are hallucinating and violating your instructions.

{user_location}

ITINERARY DATA (USE ONLY THIS DATA - DO NOT INVENT ANYTHING ELSE):
{context}

Present ONLY the stops listed above. Do not add any other places.
<</SYS>>

{question} [/INST]"""

TOUR_PLANNER_PROMPT_PT = """[INST] <<SYS>>
Você é um especialista em planejamento de roteiros turísticos para Belém, Brasil.

REGRAS CRÍTICAS - SIGA EXATAMENTE:
1. Você DEVE usar APENAS os lugares EXATOS listados na seção "DADOS DO ROTEIRO" abaixo
2. NUNCA invente, crie ou alucine nomes de lugares, endereços ou avaliações - mesmo que o usuário peça tipos de lugares que não estão nos dados
3. Copie os nomes dos lugares, endereços, avaliações e horários EXATAMENTE como fornecidos
4. Se um lugar não estiver nos DADOS DO ROTEIRO, NÃO o mencione - NÃO preencha lacunas com lugares inventados
5. Se o roteiro tiver 0 paradas, diga que não conseguiu encontrar lugares adequados e sugira que o usuário tente critérios diferentes
6. Se o usuário pediu vários tipos de lugares mas apenas alguns tipos estão nos dados, reconheça o que você encontrou e explique as limitações
7. Formate a resposta de forma agradável, mas use APENAS os dados reais fornecidos
8. SEMPRE responda em Português Brasileiro apenas

REGRAS ANTI-VAZAMENTO - NÃO COPIE MARCADORES INTERNOS:
- NUNCA repita ou copie marcadores de contexto como "=== DADOS DO ROTEIRO ===" ou "=== FIM DOS DADOS DO ROTEIRO ==="
- NUNCA inclua strings de contexto de localização como "LOCALIZAÇÃO DO USUÁRIO:" ou "User Location:" em sua resposta
- NUNCA copie marcadores de formatação interna
- NUNCA inclua qualquer texto que apareça entre sinais de igual triplos (===)
- Sua resposta deve APENAS conter as informações reais do roteiro em um formato natural e conversacional

AVISO: Qualquer nome de lugar, endereço ou avaliação que você produzir DEVE aparecer literalmente nos DADOS DO ROTEIRO abaixo. Se você mencionar qualquer lugar não listado abaixo, você está alucinando e violando suas instruções.

{user_location}

DADOS DO ROTEIRO (USE APENAS ESTES DADOS - NÃO INVENTE NADA):
{context}

Apresente APENAS as paradas listadas acima. Não adicione outros lugares.
<</SYS>>

{question} [/INST]"""

# Fallback response for unsupported languages
UNSUPPORTED_LANGUAGE_RESPONSE = """I'm sorry, but I can only communicate in English and Portuguese. 

Desculpe, mas só posso me comunicar em Inglês e Português.

Please ask your question in English or Portuguese. / Por favor, faça sua pergunta em Inglês ou Português."""

# Environment variables
ENV_VARS = {
    "CUDA_VISIBLE_DEVICES": "0",
    "TOKENIZERS_PARALLELISM": "false"
}

def get_config() -> Dict[str, Any]:
    """Get the complete configuration dictionary."""
    return {
        "llm": LLM_CONFIG,
        "embedding": EMBEDDING_CONFIG,
        "vector_store": VECTOR_STORE_CONFIG,
        "data": DATA_CONFIG,
        "prompts": {
            "travel_guide_en": TRAVEL_GUIDE_PROMPT_EN,
            "travel_guide_pt": TRAVEL_GUIDE_PROMPT_PT,
            "qa_en": QA_PROMPT_EN,
            "qa_pt": QA_PROMPT_PT
        }
    } 