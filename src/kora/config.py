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
    # Interface web fora desta máquina (Tailscale Serve): hosts aceitos além do local e e-mails
    # autorizados a entrar por eles. Vazio = só acesso local.
    web_hosts: str = ""
    web_allowed_users: str = ""

    @property
    def web_hosts_lista(self) -> set[str]:
        return {h.strip().lower() for h in self.web_hosts.split(",") if h.strip()}

    @property
    def web_users_lista(self) -> set[str]:
        return {u.strip().lower() for u in self.web_allowed_users.split(",") if u.strip()}

    @property
    def heartbeat_path(self) -> Path:
        return self.db_path.parent / "worker.heartbeat"

    @property
    def execucao_path(self) -> Path:
        return self.db_path.parent / "ultima_execucao.json"

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
