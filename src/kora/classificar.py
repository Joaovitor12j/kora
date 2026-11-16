import logging

from .config import Settings
from .extractors.meta import Meta
from .llm import Provider
from .llm.prompt import system_prompt, user_prompt
from .llm.schema import SCHEMA, parse

log = logging.getLogger("kora.classificar")


def classificar(meta: Meta, provider: Provider | None, settings: Settings, tags_existentes: list[str]) -> bool:
    """Preenche título, resumo, categoria e tags. Sem IA ou com falha, a nota fica pendente."""
    if provider is None:
        return False
    extra = {"imagens": meta.imagens_visao} if meta.imagens_visao and provider.suporta_visao else {}
    try:
        c = parse(provider.complete(
            system_prompt(tags_existentes), user_prompt(meta, settings.llm_max_chars), SCHEMA, **extra))
    except Exception as e:
        log.warning("IA %s falhou para %s: %s: %s", provider.label, meta.url, type(e).__name__, e)
        return False
    meta.titulo, meta.resumo, meta.pontos_chave = c.titulo, c.resumo, c.pontos_chave
    meta.categoria, meta.tags, meta.ia = c.categoria, c.tags, provider.label
    return True
