from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "ai_clipper"

    media_dir: Path = Path("./media")
    models_dir: Path = Path("./models")

    whisper_medium_dir: str = "whisper-medium"
    whisper_large_v3_dir: str = "whisper-large-v3"
    llama_model_file: str = "llama-3.1-8b-q5/llama-3.1-8b-instruct-q5_k_m.gguf"

    cuda_visible_devices: str = "0"
    whisper_compute_type: str = "float16"
    llama_n_gpu_layers: int = -1

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def whisper_medium_path(self) -> Path:
        return self.models_dir / self.whisper_medium_dir

    @property
    def whisper_large_v3_path(self) -> Path:
        return self.models_dir / self.whisper_large_v3_dir

    @property
    def llama_model_path(self) -> Path:
        return self.models_dir / self.llama_model_file

    @property
    def originals_dir(self) -> Path:
        return self.media_dir / "originals"

    @property
    def exports_dir(self) -> Path:
        return self.media_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        return self.media_dir / "logs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
