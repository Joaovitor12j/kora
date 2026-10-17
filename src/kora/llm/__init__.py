from ..config import Settings
from .anthropic_provider import AnthropicProvider
from .base import Provider
from .deepseek import DeepSeekProvider
from .ollama import OllamaProvider

PROVEDORES = ("anthropic", "deepseek", "ollama")


def build_provider(s: Settings) -> Provider | None:
    """O provedor escolhido em LLM_PROVIDER, ou None se a IA estiver desligada.

    Escolha mal configurada (nome errado, chave ausente) falha na partida, não na primeira nota.
    """
    nome = s.llm_provider.strip().lower()
    if not nome:
        return None
    if nome == "anthropic":
        _exigir(nome, "ANTHROPIC_API_KEY", s.anthropic_api_key)
        return AnthropicProvider(s.anthropic_api_key, s.anthropic_model, s.llm_timeout)
    if nome == "deepseek":
        _exigir(nome, "DEEPSEEK_API_KEY", s.deepseek_api_key)
        return DeepSeekProvider(s.deepseek_api_key, s.deepseek_model, s.deepseek_base_url, s.llm_timeout)
    if nome == "ollama":
        return OllamaProvider(s.ollama_model, s.ollama_base_url, s.ollama_timeout)
    raise ValueError(f"LLM_PROVIDER inválido: {nome!r} (use {', '.join(PROVEDORES)} ou deixe vazio)")


def _exigir(nome: str, variavel: str, valor: str) -> None:
    if not valor:
        raise ValueError(f"LLM_PROVIDER={nome} exige {variavel} no .env")


__all__ = ["Provider", "build_provider"]
