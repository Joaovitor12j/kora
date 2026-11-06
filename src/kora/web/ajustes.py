"""Leitura e gravação das configurações do painel: .env, categorias e intervalo dos lotes."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from .. import taxonomia
from ..agenda import TIMER, _systemctl, conferir_timer, iniciar_lote
from ..config import Settings, get_settings
from ..llm import PROVEDORES, build_provider

ENV = Path(".env")
DROPIN = Path.home() / ".config/systemd/user" / f"{TIMER}.d" / "intervalo.conf"

WHISPER_MODELOS = ("tiny", "base", "small", "medium", "large-v3")
# Chaves de API: o painel grava mas nunca devolve o valor.
SEGREDOS = {"ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"}
TEXTOS = {"ANTHROPIC_MODEL", "DEEPSEEK_MODEL", "OLLAMA_MODEL", "OLLAMA_BASE_URL", "WHISPER_LANGUAGE"}
ACESSO = {"WEB_HOSTS", "WEB_ALLOWED_USERS"}
INTEIROS = {"MAX_AUDIO_MINUTES": (1, 600), "LLM_MAX_CHARS": (1000, 100000), "LLM_TIMEOUT": (5, 600)}
CAMPOS = SEGREDOS | TEXTOS | ACESSO | INTEIROS.keys() | {"LLM_PROVIDER", "WHISPER_MODEL"}


class ErroDeAjuste(ValueError):
    pass


def ler_env(path: Path | None = None) -> dict[str, str]:
    path = path or ENV
    valores = {}
    try:
        linhas = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valores
    for linha in linhas:
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", linha)
        if m:
            valores[m.group(1)] = m.group(2).strip("\"'")
    return valores


def gravar_env(mudancas: dict[str, str], path: Path | None = None) -> None:
    """Troca as chaves existentes no lugar e acrescenta as novas no fim; comentários e o resto ficam."""
    path = path or ENV
    try:
        linhas = path.read_text(encoding="utf-8").splitlines()
        modo = path.stat().st_mode & 0o777
    except OSError:
        linhas, modo = [], 0o600
    pendentes = dict(mudancas)
    for i, linha in enumerate(linhas):
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=", linha)
        if m and m.group(1) in pendentes:
            linhas[i] = f"{m.group(1)}={pendentes.pop(m.group(1))}"
    linhas += [f"{k}={v}" for k, v in pendentes.items()]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.chmod(tmp, modo)  # .env tem chaves: nunca mais aberto que o original
    tmp.replace(path)
    get_settings.cache_clear()


def validar(entrada: dict) -> dict[str, str]:
    """Só as chaves conhecidas, já validadas. Chave de API vazia significa 'manter a salva'."""
    limpo: dict[str, str] = {}
    for chave, valor in entrada.items():
        if chave not in CAMPOS:
            raise ErroDeAjuste(f"Campo desconhecido: {chave}")
        valor = str(valor).strip()
        if "\n" in valor or "\r" in valor:
            raise ErroDeAjuste(f"{chave} não pode ter quebra de linha")
        if chave in SEGREDOS and not valor:
            continue
        if chave == "LLM_PROVIDER" and valor not in ("", *PROVEDORES):
            raise ErroDeAjuste(f"Provedor inválido: {valor}")
        if chave == "WHISPER_MODEL" and valor not in WHISPER_MODELOS:
            raise ErroDeAjuste(f"Modelo de transcrição inválido: {valor}")
        if chave == "OLLAMA_BASE_URL" and not re.match(r"^https?://\S+$", valor):
            raise ErroDeAjuste("O endereço do Ollama deve começar com http:// ou https://")
        itens = [i.strip() for i in valor.split(",") if i.strip()]
        if chave == "WEB_HOSTS" and not all(re.fullmatch(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?", i.lower()) for i in itens):
            raise ErroDeAjuste("WEB_HOSTS aceita só nomes de host separados por vírgula, sem http:// nem porta")
        if chave == "WEB_ALLOWED_USERS" and not all(re.fullmatch(r"[^@\s,]+@[^@\s,]+", i) for i in itens):
            raise ErroDeAjuste("WEB_ALLOWED_USERS aceita só e-mails separados por vírgula")
        if chave in ACESSO:
            valor = ",".join(itens)
        if chave in INTEIROS:
            menor, maior = INTEIROS[chave]
            if not valor.isdigit() or not menor <= int(valor) <= maior:
                raise ErroDeAjuste(f"{chave} deve ser um número de {menor} a {maior}")
        limpo[chave] = valor
    return limpo


def acesso_mudou(env_validado: dict[str, str], settings: Settings) -> bool:
    """True se o envio altera quem pode entrar de fora. Valores iguais aos atuais não contam."""
    atual = {"WEB_HOSTS": ",".join(sorted(settings.web_hosts_lista)),
             "WEB_ALLOWED_USERS": ",".join(sorted(settings.web_users_lista))}
    return any(",".join(sorted(i.lower() for i in env_validado[k].split(",") if i)) != atual[k]
               for k in ACESSO if k in env_validado)


def estado(settings: Settings) -> dict:
    """O que a tela mostra. Chaves de API só dizem se existem."""
    env = ler_env()
    return {
        "provedor": settings.llm_provider,
        "provedores": list(PROVEDORES),
        "anthropic_model": settings.anthropic_model,
        "deepseek_model": settings.deepseek_model,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "chaves": {k: bool(env.get(k)) for k in sorted(SEGREDOS)},
        "web_hosts": settings.web_hosts,
        "web_allowed_users": settings.web_allowed_users,
        "whisper_model": settings.whisper_model,
        "whisper_modelos": list(WHISPER_MODELOS),
        "whisper_language": settings.whisper_language,
        "max_audio_minutes": settings.max_audio_minutes,
        "llm_max_chars": settings.llm_max_chars,
        "llm_timeout": int(settings.llm_timeout),
        "lotes": ler_intervalo(),
        "categorias": [{"nome": n, "descricao": d} for n, d in taxonomia.carregar().items()],
        "fallback": taxonomia.FALLBACK,
    }


# --- categorias ---------------------------------------------------------------------------------

def validar_categorias(lista: list[dict]) -> dict[str, str]:
    cats: dict[str, str] = {}
    vistos = set()
    for item in lista:
        nome = str(item.get("nome", "")).strip()
        descricao = str(item.get("descricao", "")).strip()
        if not nome:
            continue
        if re.search(r'[/\\:*?"<>|\n]', nome) or nome.startswith("."):
            raise ErroDeAjuste(f"O nome \"{nome}\" vira pasta no vault e não pode ter / \\ : * ? \" < > |")
        if nome.lower() in vistos:
            raise ErroDeAjuste(f"A categoria \"{nome}\" aparece duas vezes")
        if not descricao:
            raise ErroDeAjuste(f"Descreva o que entra em \"{nome}\"; a IA usa isso para decidir")
        vistos.add(nome.lower())
        cats[nome] = descricao
    if taxonomia.FALLBACK.lower() not in vistos:
        cats[taxonomia.FALLBACK] = taxonomia.PADRAO[taxonomia.FALLBACK]
    if len(cats) < 2:
        raise ErroDeAjuste("Mantenha pelo menos uma categoria além de \"outros\"")
    return cats


# --- intervalo dos lotes ------------------------------------------------------------------------

PADRAO_LOTES = {"primeiro_min": 60, "intervalo_h": 8}


def ler_intervalo(path: Path | None = None) -> dict:
    path = path or DROPIN
    lotes = dict(PADRAO_LOTES)
    try:
        texto = path.read_text(encoding="utf-8")
    except OSError:
        return lotes
    if m := re.findall(r"^OnActiveSec=(\d+)min\s*$", texto, re.M):
        lotes["primeiro_min"] = int(m[-1])
    if m := re.findall(r"^OnUnitInactiveSec=(\d+)h\s*$", texto, re.M):
        lotes["intervalo_h"] = int(m[-1])
    return lotes


def validar_intervalo(primeiro_min, intervalo_h) -> dict:
    try:
        primeiro, intervalo = int(primeiro_min), int(intervalo_h)
    except (TypeError, ValueError):
        raise ErroDeAjuste("O intervalo dos lotes deve ser um número") from None
    if not 1 <= primeiro <= 1440:
        raise ErroDeAjuste("O primeiro lote deve sair de 1 a 1440 minutos depois de ligar")
    if not 1 <= intervalo <= 168:
        raise ErroDeAjuste("O intervalo entre lotes deve ser de 1 a 168 horas")
    return {"primeiro_min": primeiro, "intervalo_h": intervalo}


def gravar_intervalo(lotes: dict, path: Path | None = None) -> bool:
    """Grava o drop-in do systemd. True se o conteúdo mudou."""
    path = path or DROPIN
    # Uma linha vazia zera TODOS os timers do unit (qualquer On*Sec), então só pode haver uma,
    # antes dos novos valores; uma segunda apagaria o que acabou de ser definido.
    texto = ("[Timer]\nOnActiveSec=\n" f"OnActiveSec={lotes['primeiro_min']}min\n"
             f"OnUnitInactiveSec={lotes['intervalo_h']}h\n")
    try:
        if path.read_text(encoding="utf-8") == texto:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    return True


# --- aplicar e testar ---------------------------------------------------------------------------

@dataclass
class Passo:
    nome: str
    ok: bool
    detalhe: str = ""


def _sistema(*args: str) -> tuple[bool, str]:
    r = _systemctl(*args)
    if r is None:
        return False, "systemctl indisponível"
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def aplicar(env: dict[str, str], categorias: dict[str, str] | None, lotes: dict | None,
            reiniciar: bool = True) -> list[Passo]:
    """Grava tudo e reinicia o que lê configuração na partida. O worker é um lote: lê o .env no próximo."""
    passos = []
    if env:
        gravar_env(env)
        passos.append(Passo("Configurações gravadas no .env", True))
    if categorias is not None:
        taxonomia.salvar(categorias)
        passos.append(Passo("Categorias gravadas", True))
    mudou_timer = bool(lotes) and gravar_intervalo(lotes)
    if mudou_timer:
        passos.append(Passo("Intervalo dos lotes gravado", True))
    if not reiniciar:
        return passos
    if mudou_timer:
        ok, det = _sistema("daemon-reload")
        ok2, det2 = _sistema("restart", TIMER)
        passos.append(Passo("Agenda dos lotes atualizada", ok and ok2, det or det2))
        if ok and ok2 and (defeito := conferir_timer()):
            passos.append(Passo("Agenda dos lotes conferida", False, defeito))
    if env or categorias is not None:
        ok, det = _sistema("restart", "kora-bot.service")
        passos.append(Passo("Bot reiniciado", ok, "" if ok else det or "serviço não instalado"))
    return passos


def testar_conexao(provedor: str, overrides: dict[str, str]) -> Passo:
    """Chama o provedor com uma tarefa mínima, usando os valores da tela e, na falta, os salvos."""
    s = get_settings()
    campos = {"llm_provider": provedor}
    for chave, valor in overrides.items():
        if valor:
            campos[chave.lower()] = valor
    try:
        provider = build_provider(s.model_copy(update=campos))
    except ValueError as e:
        return Passo("Teste", False, str(e))
    if provider is None:
        return Passo("Teste", False, "Escolha um provedor para testar")
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
              "additionalProperties": False}
    try:
        resposta = provider.complete("Responda só com o JSON pedido.", 'Devolva {"ok": true}.', schema)
    except Exception as e:  # noqa: BLE001 — qualquer falha do provedor é resultado do teste
        return Passo(provider.label, False, f"{type(e).__name__}: {str(e)[:240]}")
    return Passo(provider.label, "ok" in resposta, "respondeu" if "ok" in resposta else resposta[:160])


def modelos_ollama(base_url: str) -> list[str]:
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=4)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
    except (httpx.HTTPError, ValueError, KeyError):
        return []


def lote_agora() -> str:
    return iniciar_lote()
