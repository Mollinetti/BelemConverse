from pydantic import BaseModel, Field, FilePath, DirectoryPath
from typing import Optional
from pathlib import Path

class BelemError(Exception):
    """Base exception for all application errors"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ConfigError(BelemError):
    """Configuration-related errors"""

class PathConfig(BaseModel):
    llm_model: FilePath = Field(..., description="Path to LLM model file")
    attractions_data: FilePath = Field(..., description="Path to attractions CSV data")
    chroma_db: DirectoryPath = Field(..., description="Path to ChromaDB directory")

class ModelParams(BaseModel):
    temperature: float = Field(0.1, ge=0, le=1)
    max_tokens: int = Field(2000, gt=0)
    n_ctx: int = Field(4096, gt=0)
    n_gpu_layers: int = Field(35, ge=0)
    top_p: float = Field(1.0, ge=0, le=1)
