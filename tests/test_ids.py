from kora.config import Settings
from kora.extractors.meta import Meta
from kora.ids import com_id
from kora.vault import ler_nota, render, write_note


def test_id_depende_so_da_url():
    a = Meta(url="https://x.com/a/status/1", plataforma="x", titulo="um")
    b = Meta(url="https://x.com/a/status/1", plataforma="x", titulo="outro título")
    assert a.id == b.id and a.id.startswith("k") and len(a.id) == 9
    assert a.id != Meta(url="https://x.com/a/status/2", plataforma="x", titulo="um").id


def test_nota_nova_tem_id_e_alias(tmp_path):
    s = Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                 db_path=tmp_path / "q.sqlite", _env_file=None)
    m = Meta(url="https://x.com/a/status/1", plataforma="x", titulo="T", categoria="outros", resumo="r")
    p = write_note(s.saved_dir, m, 1)
    texto = p.read_text(encoding="utf-8")
    assert f'url: "https://x.com/a/status/1"\nid: {m.id}\naliases: [{m.id}]\n' in texto
    lida, _ = ler_nota(p)
    assert lida.id == m.id and render(lida, lida.criado) == texto


def test_com_id_em_nota_antiga_e_idempotente():
    antiga = '---\ntipo: link\nurl: "u"\nautor: ""\ntags: []\n---\n\n# T\n'
    novo = com_id(antiga, "kabc")
    assert 'url: "u"\nid: kabc\naliases: [kabc]\nautor' in novo and com_id(novo, "kabc") == novo
    com_alias = antiga.replace('autor: ""', 'aliases: [meu]\nautor: ""')
    assert "aliases: [meu]" in com_id(com_alias, "kabc") and "aliases: [kabc]" not in com_id(com_alias, "kabc")
    assert com_id("sem frontmatter", "k") == "sem frontmatter"
