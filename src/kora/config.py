from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    telegram_allowed_chat_id: int
    vault_path: Path
    vault_saved_dir: str = "Referencias/Salvos"
    db_path: Path = Path("data/queue.sqlite")
    anthropic_api_key: str = ""
    whisper_model: str = "small"
    whisper_language: str = ""  # vazio = detectar o idioma
    max_audio_minutes: int = 30

    @property
    def inbox_dir(self) -> Path:
        """Pasta de entrada; a Fase 3 move a nota para a pasta da categoria."""
        return self.vault_path / self.vault_saved_dir / "_inbox"


@lru_cache
def get_settings() -> Settings:
    return Settings()
