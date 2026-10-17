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
    log_level: str = "INFO"
    # IA: um único provedor ativo (anthropic, deepseek ou ollama).
    # Vazio desliga a categorização (a nota fica em _inbox com status pendente).
    llm_provider: str = ""
    llm_timeout: float = 60.0
    llm_max_chars: int = 12000  # limite de conteúdo enviado ao modelo (custo e contexto)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"
    ollama_timeout: float = 300.0  # modelo local pode precisar carregar na memória
    whisper_model: str = "small"
    whisper_language: str = ""  # vazio = detectar o idioma
    max_audio_minutes: int = 30

    @property
    def heartbeat_path(self) -> Path:
        return self.db_path.parent / "worker.heartbeat"

    @property
    def saved_dir(self) -> Path:
        return self.vault_path / self.vault_saved_dir

    @property
    def inbox_dir(self) -> Path:
        """Pasta de entrada; a Fase 3 move a nota para a pasta da categoria."""
        return self.vault_path / self.vault_saved_dir / "_inbox"


@lru_cache
def get_settings() -> Settings:
    return Settings()
