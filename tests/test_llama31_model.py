"""
Quick test script to verify Llama 3.1 8B model loads and produces Portuguese responses.
"""
import sys
from pathlib import Path

# Add project root to path

from belem_converse.utils.models import ModelManager
from belem_converse.utils.config import LLM_CONFIG
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_model_loading():
    """Test that the model loads correctly."""
    logger.info("Testing model loading...")
    logger.info(f"Model path from config: {LLM_CONFIG['model_path']}")
    
    try:
        llm = ModelManager.get_llm()
        logger.info("✅ Model loaded successfully!")
        logger.info(f"Model type: {type(llm)}")
        return llm
    except Exception as e:
        logger.error(f"❌ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_portuguese_response(llm):
    """Test Portuguese language quality."""
    logger.info("\n" + "="*70)
    logger.info("Testing Portuguese language quality...")
    logger.info("="*70)
    
    # Simple Portuguese test query
    test_prompt = """[INST] <<SYS>>
Você é um guia turístico para Belém, Brasil. Responda APENAS em Português Brasileiro.

REGRAS CRÍTICAS:
1. Use APENAS as informações fornecidas - NUNCA invente informações
2. Se não souber, diga "Não tenho essa informação"
3. SEMPRE responda em Português Brasileiro apenas

Contexto: Você tem informações sobre restaurantes em Belém.
<</SYS>>

Olá! Você pode me recomendar um bom restaurante em Belém? [/INST]"""
    
    try:
        logger.info("Sending Portuguese test query...")
        response = llm.invoke(test_prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"\nResponse received ({len(response_text)} chars):")
        logger.info("-" * 70)
        logger.info(response_text)
        logger.info("-" * 70)
        
        # Check for Portuguese indicators
        portuguese_indicators = ['restaurante', 'Belém', 'você', 'pode', 'recomendar', 'bom', 'boa']
        found_indicators = [ind for ind in portuguese_indicators if ind.lower() in response_text.lower()]
        
        if found_indicators:
            logger.info(f"✅ Portuguese language detected: {found_indicators}")
        else:
            logger.warning("⚠️  Limited Portuguese indicators found in response")
        
        # Check for English (should be minimal)
        english_indicators = ['restaurant', 'can you', 'recommend', 'good']
        found_english = [ind for ind in english_indicators if ind.lower() in response_text.lower()]
        
        if found_english and len(found_english) > 2:
            logger.warning(f"⚠️  English detected in response: {found_english}")
        else:
            logger.info("✅ Response appears to be primarily in Portuguese")
        
        return response_text
        
    except Exception as e:
        logger.error(f"❌ Portuguese test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_instruction_following(llm):
    """Test that the model follows instructions and doesn't hallucinate."""
    logger.info("\n" + "="*70)
    logger.info("Testing instruction following (no hallucination)...")
    logger.info("="*70)
    
    # Test with explicit instruction to not invent places
    test_prompt = """[INST] <<SYS>>
Você é um guia turístico para Belém, Brasil. 

REGRAS CRÍTICAS:
1. Use APENAS as informações fornecidas no contexto
2. NUNCA invente ou crie nomes de lugares
3. Se não tiver informações, diga "Não tenho informações sobre isso"

Contexto fornecido:
- Restaurante Açaí Do Irmão está localizado em Belém
- Restaurante Barao Açaí está localizado em Belém

NÃO mencione nenhum outro restaurante que não esteja listado acima.
<</SYS>>

Quais restaurantes você conhece em Belém? [/INST]"""
    
    try:
        logger.info("Sending instruction following test query...")
        response = llm.invoke(test_prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"\nResponse received ({len(response_text)} chars):")
        logger.info("-" * 70)
        logger.info(response_text)
        logger.info("-" * 70)
        
        # Check that only provided places are mentioned
        provided_places = ['Açaí Do Irmão', 'Barao Açaí']
        mentioned_places = [place for place in provided_places if place.lower() in response_text.lower()]
        
        logger.info(f"✅ Provided places mentioned: {mentioned_places}")
        
        # Check for common hallucination patterns (other restaurant names not in context)
        common_restaurant_names = ['Ver-o-Peso', 'Lá em Casa', 'Remanso do Bosque', 'Casa do Saulo']
        hallucinated = [name for name in common_restaurant_names if name.lower() in response_text.lower()]
        
        if hallucinated:
            logger.warning(f"⚠️  Possible hallucination detected: {hallucinated}")
        else:
            logger.info("✅ No obvious hallucinations detected")
        
        # Check for instruction compliance phrases
        compliance_phrases = ['não tenho', 'informações fornecidas', 'listado acima', 'contexto']
        found_compliance = [phrase for phrase in compliance_phrases if phrase.lower() in response_text.lower()]
        
        if found_compliance:
            logger.info(f"✅ Instruction compliance indicators found: {found_compliance}")
        
        return response_text
        
    except Exception as e:
        logger.error(f"❌ Instruction following test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    logger.info("="*70)
    logger.info("Llama 3.1 8B Model Test Suite")
    logger.info("="*70)
    
    # Test 1: Model loading
    llm = test_model_loading()
    
    if llm:
        # Test 2: Portuguese quality
        portuguese_result = test_portuguese_response(llm)
        
        # Test 3: Instruction following
        instruction_result = test_instruction_following(llm)
        
        logger.info("\n" + "="*70)
        logger.info("Test Summary")
        logger.info("="*70)
        logger.info(f"Model loading: {'✅ PASSED' if llm else '❌ FAILED'}")
        logger.info(f"Portuguese quality: {'✅ PASSED' if portuguese_result else '❌ FAILED'}")
        logger.info(f"Instruction following: {'✅ PASSED' if instruction_result else '❌ FAILED'}")
    else:
        logger.error("Cannot proceed with tests - model failed to load")
