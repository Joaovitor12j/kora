import json

from helpers import BOM, Fake
from kora.classificar import classificar
from kora.config import Settings
from kora.extractors.meta import Meta
from kora.ferramenta_itens import ler_secao, limpar, linhas_secao
from kora.ferramentas import atribuir, escrever_catalogo, juntar, sem_ferramentas
from kora.llm.schema import Classificacao
from kora.vault import ler_nota, render, write_note

TEXTO = "Use Remotion https://remotion.dev/ e o repo https://github.com/a/b"


def cfg(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                    db_path=tmp_path / "q.sqlite", _env_file=None)


def test_limpar_so_aceita_url_que_esta_no_texto():
    itens = [{"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Inventada", "url": "https://x.io"},
             "Claude Code", {"nome": "  ", "url": ""}, {"nome": "remotion", "url": ""}, {"nome": "a[b],c", "url": ""}]
    assert limpar(itens, TEXTO) == [
        {"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Inventada", "url": ""},
        {"nome": "Claude Code", "url": ""}, {"nome": "a b c", "url": ""}]
    assert len(limpar([{"nome": f"f{i}", "url": ""} for i in range(20)])) == 8


def test_secao_faz_round_trip():
    itens = [{"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Claude Code", "url": ""}]
    assert ler_secao("\n".join(linhas_secao(itens))) == itens


def test_schema_aceita_resposta_sem_ferramentas_e_com_lixo():
    assert Classificacao(**BOM).ferramentas == []
    assert Classificacao(**{**BOM, "ferramentas": "nenhuma"}).ferramentas == []


def test_classificar_preenche_ferramentas(tmp_path):
    resp = {**BOM, "ferramentas": [{"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Falsa", "url": "https://falsa.io"}]}
    m = Meta(url="u", plataforma="x", titulo="T", descricao=TEXTO)
    assert classificar(m, Fake("a", json.dumps(resp)), cfg(tmp_path), [])
    assert m.ferramentas == [{"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Falsa", "url": ""}]


def test_nota_com_ferramentas_faz_round_trip(tmp_path):
    s = cfg(tmp_path)
    m = Meta(url="u", plataforma="x", titulo="T", categoria="design", resumo="r", ia="a/m", descricao="d" * 250,
             ferramentas=[{"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Claude Code", "url": ""}])
    p = write_note(s.saved_dir / "design", m, 1)
    texto = p.read_text(encoding="utf-8")
    assert "ferramentas: [Remotion, Claude Code]" in texto and "## Ferramentas\n- [Remotion](https://remotion.dev)" in texto
    lida, _ = ler_nota(p)
    assert lida.ferramentas == m.ferramentas and render(lida, lida.criado) == texto


def nota(s, titulo, ferr, extra_desc=""):
    m = Meta(url=f"u/{titulo}", plataforma="x", titulo=titulo, categoria="design", resumo="r", ia="a/m",
             descricao=TEXTO + extra_desc, ferramentas=ferr)
    return write_note(s.saved_dir / "design", m, 1)


def test_backfill_pergunta_so_as_notas_sem_marca(tmp_path):
    s = cfg(tmp_path)
    antiga = nota(s, "Antiga", [])
    texto = antiga.read_text(encoding="utf-8").replace("ferramentas: []\n", "")  # nota de antes do campo
    antiga.write_text(texto, encoding="utf-8")
    nota(s, "Nova", [])  # já tem `ferramentas: []`
    assert [n.name[-9:] for n, _ in sem_ferramentas(s.saved_dir)] == ["Antiga.md"]
    ia = Fake("a", json.dumps({"ferramentas": [{"nome": "Remotion", "url": "https://remotion.dev"}]}))
    assert atribuir(s, ia, aplicar=False) == (1, 0, 0) and "ferramentas:" not in antiga.read_text(encoding="utf-8")
    assert atribuir(s, ia, aplicar=True) == (1, 0, 0)
    lida, _ = ler_nota(antiga)
    assert lida.ferramentas == [{"nome": "Remotion", "url": "https://remotion.dev"}]
    assert "ferramentas: [Remotion]\ntags:" in antiga.read_text(encoding="utf-8")
    assert list(sem_ferramentas(s.saved_dir)) == []
    vazio = Fake("a", json.dumps({"ferramentas": []}))
    antiga2 = nota(s, "Antiga2", [])
    antiga2.write_text(antiga2.read_text(encoding="utf-8").replace("ferramentas: []\n", ""), encoding="utf-8")
    assert atribuir(s, vazio, aplicar=True) == (0, 1, 0) and list(sem_ferramentas(s.saved_dir)) == []  # marca `[]`


def test_catalogo_junta_grafias_e_notas(tmp_path):
    s = cfg(tmp_path)
    nota(s, "Um", [{"nome": "Remotion", "url": "https://remotion.dev"}, {"nome": "Claude Code", "url": ""}])
    nota(s, "Dois", [{"nome": "remotion", "url": ""}])
    itens = juntar(s.saved_dir)
    assert [i["nome"] for i in itens] == ["Remotion", "Claude Code"]
    assert itens[0]["url"] == "https://remotion.dev" and len(itens[0]["notas"]) == 2
    caminho, n = escrever_catalogo(s, "2026-11-16")
    assert n == 2 and "| Remotion | https://remotion.dev |" in caminho.read_text(encoding="utf-8")
    caminho.write_text(caminho.read_text(encoding="utf-8") + "\nminha anotação\n", encoding="utf-8")
    escrever_catalogo(s, "2026-11-17")
    assert "minha anotação" in caminho.read_text(encoding="utf-8")  # só o bloco automático é reescrito
    assert [x for x in s.saved_dir.rglob("Ferramentas.md")] == [caminho] and juntar(s.saved_dir) == itens  # o catálogo não conta como nota


def test_url_so_vale_se_for_da_ferramenta():
    from kora.ferramenta_itens import url_combina
    assert url_combina("Remotion", "https://remotion.dev")
    assert url_combina("godly.website", "http://godly.website")
    assert url_combina("ppt-master", "https://github.com/a/ppt-master")
    assert not url_combina("Remotion", "https://github.com/a/video-shotcraft")
    assert not url_combina("GitHub", "https://github.com/a/video-editor-skills")
    assert not url_combina("Three.js", "https://github.com/a/dioramas")


def test_limpar_tira_plataforma_e_corrige_grafia():
    itens = [{"nome": "Instagram", "url": ""}, {"nome": "Cloud Code", "url": ""}, {"nome": "claude-code", "url": ""}]
    assert limpar(itens, "") == [{"nome": "Claude Code", "url": ""}]


def test_classificar_ignora_ferramentas_de_receita(tmp_path):
    resp = {**BOM, "categoria": "receitas", "ferramentas": [{"nome": "Alho", "url": ""}]}
    m = Meta(url="u", plataforma="x", titulo="T", descricao="x")
    assert classificar(m, Fake("a", json.dumps(resp)), cfg(tmp_path), []) and m.ferramentas == []


def test_corrigir_revalida_notas_ja_gravadas(tmp_path):
    from kora.ferramentas import corrigir
    s = cfg(tmp_path)
    ruim = nota(s, "Ruim", [{"nome": "Remotion", "url": "https://github.com/a/video-shotcraft"},
                            {"nome": "Instagram", "url": ""}], extra_desc=" https://github.com/a/video-shotcraft")
    receita = Meta(url="r", plataforma="x", titulo="Receita", categoria="receitas", resumo="r", ia="a/m",
                   descricao="d" * 250, ferramentas=[{"nome": "Alho", "url": ""}])
    rp = write_note(s.saved_dir / "receitas", receita, 2)
    assert corrigir(s, aplicar=False) == 2 and "Instagram" in ruim.read_text(encoding="utf-8")
    assert corrigir(s, aplicar=True) == 2 and corrigir(s, aplicar=True) == 0
    lida, _ = ler_nota(ruim)
    assert lida.ferramentas == [{"nome": "Remotion", "url": ""}]
    assert "ferramentas: [Remotion]" in ruim.read_text(encoding="utf-8")
    texto = rp.read_text(encoding="utf-8")
    assert "ferramentas: []" in texto and "## Ferramentas" not in texto
