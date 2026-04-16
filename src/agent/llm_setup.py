from langchain_community.chat_models.llamacpp import ChatLlamaCpp
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
from .config import load_config
from .exceptions import ConfigError
import warnings
from typing import Optional

# Load configuration once at module level
_path_config, model_params = load_config()
_singleton_instance = None

def get_llm(force_reload: bool = False) -> ChatLlamaCpp:
    global _singleton_instance
    
    if _singleton_instance and not force_reload:
        return _singleton_instance
        
    try:
        # Suppress noisy warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=UserWarning)
        
        callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
        
        _singleton_instance = ChatLlamaCpp(
            model_path=str(_path_config.llm_model),
            temperature=model_params.temperature,
            max_tokens=model_params.max_tokens,
            n_ctx=model_params.n_ctx,
            n_gpu_layers=model_params.n_gpu_layers,
            top_p=model_params.top_p,
            callback_manager=callback_manager,
            verbose=True,
            streaming=True
        )
        return _singleton_instance
    
    except FileNotFoundError as e:
        raise ConfigError(f"Model file not found: {_path_config.llm_model}") from e
    except Exception as e:
        raise ConfigError(f"LLM initialization failed: {str(e)}") from e
    finally:
        warnings.resetwarnings()
