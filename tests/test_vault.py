from kora.extractors.meta import Meta
from kora.vault import render, slug, write_note

META = Meta(url="https://x.com/a/status/1", plataforma="x", titulo='Como: usar "filas" no Laravel?',
            autor="@fulano", descricao="legenda", publicado="2026-10-01")


def test_slug_strips_invalid_chars_and_limits():
    assert slug('a/b:c*d?"e') == "a b c d e"
    assert len(slug("x" * 200)) == 60
    assert slug("???") == "sem titulo"


def test_render_frontmatter():
    out = render(META, "2026-10-17")
    assert out.startswith("---\ncriado: 2026-10-17\ntipo: link\nplataforma: x\n")
    assert 'url: "https://x.com/a/status/1"' in out
    assert "status: pendente" in out
    assert "## Legenda original\nlegenda" in out


def test_write_note_is_idempotent_and_disambiguates(tmp_path):
    p1 = write_note(tmp_path, META, 1, now=0)
    assert p1.read_text(encoding="utf-8") == render(META, p1.name[:10])
    assert write_note(tmp_path, META, 1, now=0) == p1  # mesmo link -> mesmo arquivo
    other = Meta(**{**META.__dict__, "url": "https://x.com/b/status/2"})
    p2 = write_note(tmp_path, other, 2, now=0)
    assert p2 != p1 and p2.name.endswith("(2).md")
