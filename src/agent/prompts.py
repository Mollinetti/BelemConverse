from langchain_core.prompts import PromptTemplate
from .exceptions import ConfigError

def get_system_prompt() -> PromptTemplate:
    try:
        return PromptTemplate(
            template="""<s>[INST] You are a very experienced travel guide. Answer questions using ONLY the provided context. If unsure, say "I don't know".

Context: {context}

Question: {question} [/INST]</s>""",
            input_variables=["context", "question"]
        )
    except Exception as e:
        raise ConfigError(f"Prompt template creation failed: {str(e)}") from e
