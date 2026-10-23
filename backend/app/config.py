from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    youtube_api_key: str = ""
    demo_mode: bool = False
    cache_path: Path = Path("data/viettubelens.db")
    cache_ttl_seconds: int = Field(default=86_400, ge=60)
    model_version: str = "visobert-social-sentiment+visobert-toxicity-adaptive-v3"
    use_pretrained_models: bool = True
    sentiment_model_name: str = "5CD-AI/Vietnamese-Sentiment-visobert"
    toxicity_model_name: str = "dangvansam/vietnamese-toxicity"
    model_device: str = "auto"
    model_batch_size: int = Field(default=16, ge=1, le=32)
    analysis_concurrency: int = Field(default=3, ge=1, le=4)
    adaptive_initial_comments: int = Field(default=16, ge=10, le=30)
    adaptive_expand_confidence: float = Field(default=0.72, ge=0.5, le=0.95)
    toxicity_threshold: float = Field(default=0.7, ge=0, le=1)
    min_relevant_comments: int = Field(default=10, ge=1, le=100)
    confidence_threshold: float = Field(default=0.58, ge=0, le=1)

    @property
    def uses_demo_data(self) -> bool:
        return self.demo_mode or not bool(self.youtube_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
