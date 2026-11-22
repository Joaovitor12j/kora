from kora.tags import limpar_acervo, limpar_nota, normalizar_tag, normalizar_tags

NOTA = """---
criado: 2026-11-13
tipo: link
plataforma: x
categoria: design
tags: [Programação, motiongraphics, design, instagram, ia, IA, inspiração]
status: processado
---

# T
"""


def test_normalizar_tag_tira_acento_e_unifica_variantes():
    assert normalizar_tag("#Programação") == "programacao"
    assert normalizar_tag("Motion Graphics") == "motion-graphics"
    assert normalizar_tag("motiongraphics") == "motion-graphics"
    assert normalizar_tag("AI") == "ia"


def test_normalizar_tags_remove_ruido_e_duplicadas():
    assert normalizar_tags(["design", "x", "Claude", "claude", "ia"], categoria="design", plataforma="x") == ["claude", "ia"]
    assert normalizar_tags(["a", "b", "c"], maximo=2) == ["a", "b"]


def test_limpar_nota_reescreve_so_a_linha_de_tags():
    novo = limpar_nota(NOTA)
    assert "tags: [programacao, motion-graphics, ia, inspiracao]" in novo
    assert novo.replace(novo.split("tags:")[1].split("\n")[0], "") == NOTA.replace(NOTA.split("tags:")[1].split("\n")[0], "")
    assert limpar_nota(novo) == novo  # idempotente


def test_limpar_nota_ignora_o_que_nao_e_link():
    moc = "---\ntipo: nota\ntags: [moc, Programação]\n---\n"
    assert limpar_nota(moc) == moc
    assert limpar_nota("sem frontmatter") == "sem frontmatter"


def test_limpar_acervo_dry_run_nao_grava(tmp_path):
    (tmp_path / "design").mkdir()
    n = tmp_path / "design" / "a.md"
    n.write_text(NOTA, encoding="utf-8")
    alteradas, antes, depois = limpar_acervo(tmp_path)
    assert alteradas == 1 and len(antes) > len(depois) and n.read_text(encoding="utf-8") == NOTA
    limpar_acervo(tmp_path, aplicar=True)
    assert "programacao" in n.read_text(encoding="utf-8")
