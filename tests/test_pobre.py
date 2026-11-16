from kora import media
from kora.config import Settings
from kora.extractors.meta import Meta
from kora.llm.prompt import user_prompt
from kora.pobres import marcar, pobres
from kora.vault import ler_nota, render, write_note


def meta(**kw):
    base = dict(url="https://x.com/a/status/1", plataforma="x", titulo="T", descricao="bookmark this https://dotstore.io")
    return Meta(**{**base, **kw})


def test_pobre_so_sem_conteudo_e_legenda_curta():
    assert meta().pobre
    assert not meta(descricao="d" * 250).pobre
    assert not meta(conteudo="transcrição", conteudo_tipo="transcricao").pobre


def test_attach_link_usa_texto_da_pagina(monkeypatch):
    chamadas = []
    monkeypatch.setattr(media.article, "extract",
                        lambda u: chamadas.append(u) or {"conteudo": "texto da página " * 20})
    m = meta()
    media.attach_link(m)
    assert chamadas == ["https://dotstore.io"] and m.conteudo_tipo == "link" and m.link_url == "https://dotstore.io"
    assert not m.pobre


def test_attach_link_tenta_ate_dois_e_ignora_redes_e_falhas(monkeypatch):
    vistos = []

    def falha(u):
        vistos.append(u)
        raise ValueError("sem texto")

    monkeypatch.setattr(media.article, "extract", falha)
    m = meta(descricao="veja https://instagram.com/p/1 https://a.com https://b.com https://c.com")
    media.attach_link(m)
    assert vistos == ["https://a.com", "https://b.com"] and m.conteudo == "" and m.pobre


def test_attach_link_nao_age_com_conteudo_ou_legenda_longa(monkeypatch):
    monkeypatch.setattr(media.article, "extract", lambda u: (_ for _ in ()).throw(AssertionError("não devia chamar")))
    media.attach_link(meta(conteudo="já tem", conteudo_tipo="legenda"))
    media.attach_link(meta(descricao="longa " * 60 + "https://a.com"))


def test_nota_pobre_e_nota_com_link_fazem_round_trip(tmp_path):
    s = Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                 db_path=tmp_path / "q.sqlite", _env_file=None)
    pobre = write_note(s.saved_dir, meta(categoria="outros", resumo="r"), 1)
    assert "conteudo: pobre\ntags:" in pobre.read_text(encoding="utf-8")
    com_link = meta(categoria="outros", resumo="r", conteudo="texto\n\noutro", conteudo_tipo="link",
                    link_url="https://dotstore.io", titulo="Com link")
    p2 = write_note(s.saved_dir, com_link, 2)
    lida, _ = ler_nota(p2)
    assert (lida.conteudo_tipo, lida.link_url, lida.conteudo) == ("link", "https://dotstore.io", "texto\n\noutro")
    assert "conteudo: pobre" not in p2.read_text(encoding="utf-8")
    assert render(lida, lida.criado) == p2.read_text(encoding="utf-8")


def test_prompt_avisa_quando_pobre():
    assert "muito pouco texto" in user_prompt(meta(), 1000)
    assert "muito pouco texto" not in user_prompt(meta(descricao="d" * 300), 1000)


def test_marcar_notas_antigas(tmp_path):
    antiga = "---\ntipo: link\ncategoria: outros\ntags: []\nstatus: processado\n---\n\n# T\n\n## Legenda original\nbookmark\n"
    assert "conteudo: pobre\ntags: []" in marcar(antiga)
    assert marcar(marcar(antiga)) == marcar(antiga)
    (tmp_path / "a.md").write_text(antiga, encoding="utf-8")
    (tmp_path / "b.md").write_text(antiga.replace("bookmark", "longa " * 60), encoding="utf-8")
    assert [n.name for n, _ in pobres(tmp_path)] == ["a.md"]
