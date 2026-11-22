import datetime as dt

from kora import digest, temas
from kora.config import Settings
from kora.extractors.meta import Meta
from kora.relacionadas import carregar
from kora.vault import write_note

HOJE = dt.date(2026, 11, 16)


def cfg(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                    db_path=tmp_path / "q.sqlite", _env_file=None)


def nota(s, titulo, criado, cat="design", assunto="motion", ferr=(), rel=(), pobre=False):
    m = Meta(url=f"u/{titulo}", plataforma="x", titulo=titulo, categoria=cat, assunto=assunto, criado=criado,
             resumo=f"Resumo de {titulo}. Outra frase.", pontos_chave=["a"], tags=["t"], ia="a/m",
             descricao="curta" if pobre else "d" * 250, ferramentas=[{"nome": f, "url": ""} for f in ferr],
             relacionadas=list(rel))
    return write_note(s.saved_dir / cat, m, 1)


def acervo(tmp_path):
    s = cfg(tmp_path)
    nota(s, "A", "2026-11-15", ferr=["Remotion"], rel=["- [[x]]", "- [[y]]"])
    nota(s, "B", "2026-11-14", ferr=["Remotion", "Claude Code"])
    nota(s, "C", "2026-10-01", ferr=["Remotion"], rel=["- [[z]]"])
    nota(s, "D", "2026-09-01", cat="negócios", assunto="carreira")  # só 1 do tema
    nota(s, "E", "2026-11-16", pobre=True, assunto="video")
    return s


def test_agrupar_exige_tres_e_ignora_outros(tmp_path):
    s = acervo(tmp_path)
    g = temas.agrupar(carregar(s.saved_dir))
    assert list(g) == [("design", "motion")] and [m.titulo for _, m in g[("design", "motion")]] == ["A", "B", "C"]


def test_escrever_temas_cria_atualiza_e_preserva_o_resto(tmp_path):
    s = acervo(tmp_path)
    assert temas.escrever(s, "2026-11-16", aplicar=False) == [("Tema - design motion", 3, True)]
    assert not (s.saved_dir / "Temas").exists()
    temas.escrever(s, "2026-11-16", aplicar=True)
    caminho = s.saved_dir / "Temas" / "Tema - design motion.md"
    texto = caminho.read_text(encoding="utf-8")
    assert "- Remotion (3)" in texto and "- Claude Code (1)" in texto and "— Resumo de A." in texto
    assert texto.index("[[2026-11-15") < texto.index("[[2026-11-14") < texto.index("[[2026-10-01")  # mais novos primeiro
    caminho.write_text(texto + "\nminha nota\n", encoding="utf-8")
    nota(s, "F", "2026-11-16", ferr=["Remotion"])
    assert temas.escrever(s, "2026-11-17", aplicar=True) == [("Tema - design motion", 4, False)]
    novo = caminho.read_text(encoding="utf-8")
    assert "minha nota" in novo and "- Remotion (4)" in novo and novo.count("auto:tema") == 2
    assert [m.titulo for _, m in carregar(s.saved_dir) if m.titulo == "Tema"] == []  # tema não vira nota do acervo


def test_digest_conta_semana_e_revisita(tmp_path):
    s = acervo(tmp_path)
    d, caminho = digest.gerar(s, HOJE)
    assert [m.titulo for _, m in d["novas"]] == ["E", "A", "B"]
    assert d["ferramentas"][0] == ("Remotion", 2) and [m.titulo for _, m in d["fracas"]] == ["E"]
    assert [m.titulo for _, m in d["revisitar"]] == ["C"]  # velha, com ligações e não pobre
    texto = caminho.read_text(encoding="utf-8")
    assert caminho.name == "2026-W47.md" and "## Para revisitar" in texto and "## Para revisar (pouco conteúdo)" in texto
    assert "3 salvo(s)" in digest.texto_telegram(d, HOJE) and "Remotion" in digest.texto_telegram(d, HOJE)


def test_digest_sem_nota_nao_grava(tmp_path):
    s = acervo(tmp_path)
    d, caminho = digest.gerar(s, HOJE, gravar=False)
    assert caminho is None and not (s.saved_dir / "Digest").exists()


def test_digest_notas_pendentes_aparecem(tmp_path):
    s = cfg(tmp_path)
    write_note(s.inbox_dir, Meta(url="p", plataforma="x", titulo="Pend", criado="2026-11-15"), 1)
    d, _ = digest.gerar(s, HOJE, gravar=False)
    assert d["pendentes"] == 1 and "1 pendente(s) de IA" in digest.texto_telegram(d, HOJE)
