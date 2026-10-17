import pytest

from helpers import BOM
from kora.busca import buscar, formatar, normalizar, pontuar
from kora.config import Settings
from kora.extractors.meta import Meta
from kora.indice import NOME, garantir_indice
from kora.llm.schema import Classificacao
from kora.vault import ler_nota, render, write_note


@pytest.fixture
def s(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault", _env_file=None)


def nota(s, pasta, **kw):
    base = dict(url="https://x.com/a/1", plataforma="x", titulo="Título", criado="2026-10-01")
    meta = Meta(**{**base, **kw})
    return write_note(s.saved_dir / pasta, meta, 1)


def test_normalizar():
    assert normalizar("Programação ÁÉÍ Ção") == "programacao aei cao"


def test_pontuar_and_semantics_and_weights():
    m = Meta(url="u", plataforma="instagram", titulo="Motion com Claude", categoria="design", tags=["ia"],
             autor="Ana", resumo="usa animações", descricao="corpo longo com glow")
    assert pontuar(m, ["motion"]) == 5                      # título
    assert pontuar(m, ["design"]) == 4                      # categoria
    assert pontuar(m, ["animacoes"]) == 2                   # resumo, sem acento
    assert pontuar(m, ["glow"]) == 1                        # só no corpo
    assert pontuar(m, ["motion", "glow"]) == 6              # soma dos pesos
    assert pontuar(m, ["motion", "inexistente"]) == 0       # E: todos precisam aparecer


def test_buscar_ranks_ignores_index_and_limits(s):
    nota(s, "design", url="u1", titulo="Motion graphics", criado="2026-10-01")
    nota(s, "design", url="u2", titulo="Outra coisa", descricao="fala de motion no meio", criado="2026-10-05")
    nota(s, "IA", url="u3", titulo="Motion com Claude", criado="2026-10-09")
    nota(s, "IA", url="u4", titulo="Receita de bolo")
    garantir_indice(s)
    (s.saved_dir / "solta.md").write_text("# motion\nnão é do Kora", encoding="utf-8")
    achados = buscar(s, "Motion")
    assert [r.meta.url for r in achados] == ["u3", "u1", "u2"]  # empate de título: o mais novo antes; corpo por último
    assert [r.meta.url for r in buscar(s, "motion", limite=1)] == ["u3"]
    assert buscar(s, "   ") == [] and buscar(s, "zzz") == []
    assert buscar(Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=s.vault_path / "x", _env_file=None), "a") == []


def test_formatar(s):
    assert formatar([], "x") == 'Nada encontrado para "x".'
    m = Meta(url="https://u", plataforma="x", titulo="T", categoria="IA", criado="2026-10-17", resumo="Primeira. Segunda.")
    nota(s, "IA", **m.__dict__ | {"legendas": {}})
    r = buscar(s, "T")
    texto = formatar(r, "T")
    assert "1 resultado(s)" in texto and "1. T\n   IA · x · 2026-10-17" in texto and "https://u" in texto


def test_ler_nota_round_trip_processed():
    c = Classificacao(**BOM)
    m = Meta(url="https://u", plataforma="x", titulo=c.titulo, descricao="legenda", criado="2026-10-17",
             resumo=c.resumo, pontos_chave=c.pontos_chave, categoria=c.categoria, tags=c.tags, ia="ollama/gemma4")
    texto = render(m, "2026-10-17")
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "n.md"; p.write_text(texto, encoding="utf-8")
        lida, status = ler_nota(p)
    assert status == "processado" and lida.ia == "ollama/gemma4" and lida.pontos_chave == ["a", "b"]
    assert render(lida, lida.criado) == texto


def test_indice_created_once_and_never_overwritten(s):
    assert garantir_indice(s) is True
    caminho = s.saved_dir / NOME
    texto = caminho.read_text(encoding="utf-8")
    assert 'FROM "Referencias/Salvos"' in texto and "{pasta}" not in texto and texto.count("```dataview") == 6
    caminho.write_text("editado pelo usuário", encoding="utf-8")
    assert garantir_indice(s) is False and caminho.read_text(encoding="utf-8") == "editado pelo usuário"
