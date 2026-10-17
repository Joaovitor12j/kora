"""Interface web local da Kora: galeria dos links salvos, fila e ajustes.

Uso: uv run kora-web [--porta 8765]
Escuta só em 127.0.0.1 e confere Host e Origin: página de outro site não consegue acionar o painel.
"""
import argparse
import asyncio
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import uvicorn
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from .. import taxonomia
from ..agenda import consultar, ler_execucao
from ..config import get_settings
from ..db import CONCLUIDO, FALHOU, NA_FILA, PROCESSANDO, Queue
from ..logs import configurar
from ..reclassificar import pendentes as notas_pendentes
from ..status import estado_ia, idade, linhas_worker
from ..vault import ler_nota, mover_categoria
from . import acervo, ajustes
from .sigilos import chave_do_sigilo

log = logging.getLogger("kora.web")
AQUI = Path(__file__).parent
HOSTS = {"127.0.0.1", "localhost", "::1"}
PORTA_PADRAO = 8765

templates = Jinja2Templates(directory=AQUI / "templates")
templates.env.globals["sigilo_chave"] = chave_do_sigilo
templates.env.filters["data_br"] = acervo.data_br


@contextmanager
def fila():
    # SQLite não deixa a conexão cruzar threads; cada requisição abre a sua.
    q = Queue(get_settings().db_path)
    try:
        yield q
    finally:
        q.close()


# --- segurança ----------------------------------------------------------------------------------

class SoLocal:
    """Rejeita Host de fora (DNS rebinding) e escritas sem JSON ou de outra origem (CSRF)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            req = Request(scope)
            erro = None
            if urlsplit("//" + req.headers.get("host", "")).hostname not in HOSTS:
                erro = "Host não permitido"
            elif req.method not in ("GET", "HEAD", "OPTIONS"):
                origem = req.headers.get("origin")
                if origem and urlsplit(origem).hostname not in HOSTS:
                    erro = "Origem não permitida"
                elif not req.headers.get("content-type", "").startswith("application/json"):
                    erro = "Envie JSON"
            if erro:
                await JSONResponse({"erro": erro}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


# --- galeria ------------------------------------------------------------------------------------

def _filtro(req: Request) -> acervo.Filtro:
    q = req.query_params
    dias = q.get("d", "")
    try:
        limite = max(acervo.LOTE, min(int(q.get("n", acervo.LOTE)), 5000))
    except ValueError:
        limite = acervo.LOTE
    return acervo.Filtro(
        q=q.get("q", "").strip(), categoria=q.get("c", ""), plataforma=q.get("p", ""), tag=q.get("t", ""),
        dias=int(dias) if dias in ("7", "30", "365") else 0, pendentes=q.get("pend") == "1", limite=limite)


def _consulta(f: acervo.Filtro, **troca) -> str:
    """Query string do filtro atual com trocas; valor vazio tira o parâmetro. Os links do rail usam isto."""
    base = {"q": f.q, "c": f.categoria, "p": f.plataforma, "t": f.tag, "d": f.dias or "",
            "pend": "1" if f.pendentes else "", "n": ""}
    base.update(troca)
    texto = urlencode({k: v for k, v in base.items() if v not in ("", None)})
    return f"/?{texto}" if texto else "/"


async def pagina_acervo(req: Request):
    s = get_settings()
    todas = acervo.listar(s)
    f = _filtro(req)
    achadas = acervo.filtrar(todas, f)
    visiveis = achadas[:f.limite]
    ordem = list(taxonomia.carregar())
    return templates.TemplateResponse(req, "acervo.html", {
        "pagina": "salvos", "f": f, "fac": acervo.facetas(todas, ordem), "total_filtrado": len(achadas),
        "grupos": [] if f.q else acervo.agrupar_por_dia(visiveis), "lista": visiveis if f.q else [],
        "mais": _consulta(f, n=f.limite + acervo.LOTE) if len(achadas) > f.limite else "",
        "link": lambda **t: _consulta(f, **t), "categorias": ordem,
    })


def _nota_ou_404(req: Request):
    s = get_settings()
    rel = req.query_params.get("p", "")
    path = acervo.resolver(s, rel)
    if not path:
        raise HTTPException(404, "Nota não encontrada")
    entrada = next((e for e in acervo.listar(s) if e.rel == path.relative_to(s.saved_dir.resolve()).as_posix()), None)
    if not entrada:
        raise HTTPException(404, "Nota não encontrada")
    return entrada


async def pagina_nota(req: Request):
    entrada = _nota_ou_404(req)
    modelo = "_nota.html" if req.headers.get("x-fragmento") else "nota.html"
    return templates.TemplateResponse(req, modelo, {
        "e": entrada, "categorias": list(taxonomia.carregar()), "pagina": "salvos"})


async def api_categoria(req: Request):
    s = get_settings()
    corpo = await req.json()
    path = acervo.resolver(s, str(corpo.get("p", "")))
    categoria = {c.lower(): c for c in taxonomia.carregar()}.get(str(corpo.get("categoria", "")).strip().lower())
    if not path:
        return JSONResponse({"erro": "Nota não encontrada"}, status_code=404)
    if not categoria:
        return JSONResponse({"erro": "Categoria desconhecida"}, status_code=400)
    novo = mover_categoria(s, path, categoria)
    meta, _ = ler_nota(novo)
    with fila() as q:  # a fila guarda o caminho da nota; o /buscar e a correção do bot dependem dele
        item = q.by_canonica(meta.url)
        if item:
            q.set_nota(item.id, item.titulo or meta.titulo, str(novo))
    return JSONResponse({"categoria": categoria, "p": novo.relative_to(s.saved_dir).as_posix()})


# --- fila ---------------------------------------------------------------------------------------

async def pagina_fila(req: Request):
    s = get_settings()
    agora = time.time()
    with fila() as q:
        contagem = q.counts()
        itens = {NA_FILA: q.listar(NA_FILA, 30), PROCESSANDO: q.listar(PROCESSANDO, 5),
                 FALHOU: q.falhas_recentes(30)}
    agenda = consultar()
    return templates.TemplateResponse(req, "fila.html", {
        "pagina": "fila", "contagem": contagem, "itens": itens, "agora": agora, "idade": idade,
        "pendentes": [acervo._ler(s.saved_dir, p, 0) for p in notas_pendentes(s)][:30],
        "worker": [linha.lstrip("• ") for linha in linhas_worker(s, agora, agenda)],
        "rodando": agenda.rodando, "ia": estado_ia(s), "ultima": ler_execucao(s.execucao_path),
        "CONCLUIDO": CONCLUIDO, "NA_FILA": NA_FILA, "FALHOU": FALHOU, "PROCESSANDO": PROCESSANDO,
    })


async def api_lote(req: Request):
    return JSONResponse({"resultado": ajustes.lote_agora()})


# --- ajustes ------------------------------------------------------------------------------------

async def pagina_ajustes(req: Request):
    return templates.TemplateResponse(req, "ajustes.html", {
        "pagina": "ajustes", "a": ajustes.estado(get_settings())})


async def api_salvar_ajustes(req: Request):
    corpo = await req.json()
    try:
        env = ajustes.validar(corpo.get("env") or {})
        categorias = ajustes.validar_categorias(corpo["categorias"]) if "categorias" in corpo else None
        lotes = ajustes.validar_intervalo(**corpo["lotes"]) if corpo.get("lotes") else None
    except (ajustes.ErroDeAjuste, TypeError, KeyError) as e:
        return JSONResponse({"erro": str(e)}, status_code=400)
    passos = ajustes.aplicar(env, categorias, lotes)
    return JSONResponse({"passos": [p.__dict__ for p in passos], "estado": ajustes.estado(get_settings())})


async def api_testar(req: Request):
    corpo = await req.json()
    try:
        env = ajustes.validar(corpo.get("env") or {})
    except ajustes.ErroDeAjuste as e:
        return JSONResponse({"erro": str(e)}, status_code=400)
    sobre = {"anthropic_api_key": env.get("ANTHROPIC_API_KEY"), "deepseek_api_key": env.get("DEEPSEEK_API_KEY"),
             "anthropic_model": env.get("ANTHROPIC_MODEL"), "deepseek_model": env.get("DEEPSEEK_MODEL"),
             "ollama_model": env.get("OLLAMA_MODEL"), "ollama_base_url": env.get("OLLAMA_BASE_URL")}
    # Teste lento (modelo local carregando): fora do loop.
    passo = await asyncio.to_thread(ajustes.testar_conexao, str(corpo.get("provedor", "")), sobre)
    return JSONResponse(passo.__dict__)


async def api_modelos_ollama(req: Request):
    url = req.query_params.get("url") or get_settings().ollama_base_url
    return JSONResponse({"modelos": await asyncio.to_thread(ajustes.modelos_ollama, url)})


async def erro(req: Request, exc: HTTPException):
    if req.url.path.startswith("/api/"):
        return JSONResponse({"erro": exc.detail}, status_code=exc.status_code)
    return templates.TemplateResponse(req, "erro.html", {"pagina": "", "codigo": exc.status_code,
                                                         "mensagem": exc.detail}, status_code=exc.status_code)


app = Starlette(
    routes=[
        Route("/", pagina_acervo),
        Route("/nota", pagina_nota),
        Route("/fila", pagina_fila),
        Route("/ajustes", pagina_ajustes),
        Route("/api/categoria", api_categoria, methods=["POST"]),
        Route("/api/lote", api_lote, methods=["POST"]),
        Route("/api/ajustes", api_salvar_ajustes, methods=["PUT"]),
        Route("/api/ajustes/testar", api_testar, methods=["POST"]),
        Route("/api/ollama/modelos", api_modelos_ollama),
        Route("/salvos", lambda r: RedirectResponse("/")),
        Mount("/static", StaticFiles(directory=AQUI / "static"), name="static"),
    ],
    middleware=[Middleware(SoLocal)],
    exception_handlers={HTTPException: erro},
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Interface web local da Kora.")
    ap.add_argument("--porta", type=int, default=PORTA_PADRAO)
    args = ap.parse_args()
    configurar(get_settings().log_level)
    log.info("Kora em http://127.0.0.1:%s", args.porta)
    uvicorn.run(app, host="127.0.0.1", port=args.porta, log_level="warning")


if __name__ == "__main__":
    main()
