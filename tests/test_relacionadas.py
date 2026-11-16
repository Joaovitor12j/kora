from kora import worker
from kora.config import Settings
from kora.extractors.meta import Meta
from kora.relacionadas import acrescentar, carregar, parecidas, para_acervo
from kora.vault import ler_nota, render, write_note


def cfg(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                    db_path=tmp_path / "q.sqlite", _env_file=None)


def nota(s, titulo, resumo, tags, cat="design", url=None):
    m = Meta(url=url or f"u/{titulo}", plataforma="x", titulo=titulo, categoria=cat, resumo=resumo,
             pontos_chave=["a"], tags=tags, ia="a/m", descricao="d" * 250)
    return write_note(s.saved_dir / cat, m, 1)


def acervo(tmp_path):
    s = cfg(tmp_path)
    nota(s, "Motion graphics com Claude", "Animações de motion graphics geradas por agentes", ["motion-graphics", "claude"])
    nota(s, "Estilos de animação para motion", "Vinte estilos de animação e motion graphics", ["motion-graphics", "animacao"])
    nota(s, "Receita de picanha na crosta", "Picanha assada com crosta de alho", ["churrasco"], cat="receitas")
    return s


def test_parecidas_acha_o_mesmo_assunto_e_ignora_o_resto(tmp_path):
    s = acervo(tmp_path)
    novo = Meta(url="novo", plataforma="x", titulo="Motion graphics para logos", categoria="design",
                resumo="Animar logos com motion graphics", tags=["motion-graphics"])
    achadas = parecidas(carregar(s.saved_dir), novo)
    assert {p.nota.stem[11:] for p in achadas} == {"x - Motion graphics com Claude", "x - Estilos de animação para motion"}
    assert all(p.score >= 0.15 for p in achadas)


def test_parecidas_nao_inclui_a_propria_nota(tmp_path):
    s = acervo(tmp_path)
    ac = carregar(s.saved_dir)
    meta = ac[0][1]
    assert all(p.meta.url != meta.url for p in parecidas(ac, meta))
    assert parecidas([], meta) == []


def test_para_acervo_e_simetrico_no_par_obvio(tmp_path):
    ac = carregar(acervo(tmp_path).saved_dir)
    r = para_acervo(ac)
    nomes = {n.stem[11:]: [p.nota.stem[11:] for p in v] for n, v in r.items()}
    assert "x - Estilos de animação para motion" in nomes["x - Motion graphics com Claude"]
    assert nomes["x - Receita de picanha na crosta"] == []


def test_acrescentar_so_quando_nao_ha_secao(tmp_path):
    s = acervo(tmp_path)
    ac = carregar(s.saved_dir)
    (n, _), = [x for x in ac if "Claude" in x[1].titulo]
    itens = para_acervo(ac)[n]
    texto = n.read_text(encoding="utf-8")
    novo = acrescentar(texto, itens)
    assert novo.endswith(f"## Relacionado\n- [[{itens[0].nota.stem}]]\n") and novo.startswith(texto.rstrip("\n"))
    assert acrescentar(novo, itens) == novo  # idempotente
    feita_a_mao = texto + "\n## Relacionado\n- [[outra]] (mesmo assunto)\n"
    assert acrescentar(feita_a_mao, itens) == feita_a_mao


def test_secao_relacionado_faz_round_trip(tmp_path):
    s = acervo(tmp_path)
    m = Meta(url="r", plataforma="x", titulo="Com relacionadas", categoria="design", resumo="r", ia="a/m",
             descricao="d" * 250, relacionadas=["- [[a]]", "- [[b]] (mesmo assunto)"])
    p = write_note(s.saved_dir / "design", m, 9)
    lida, _ = ler_nota(p)
    assert lida.relacionadas == m.relacionadas and render(lida, lida.criado) == p.read_text(encoding="utf-8")


def test_worker_liga_nota_nova_e_avisa(tmp_path):
    s = acervo(tmp_path)
    novo = Meta(url="novo", plataforma="x", titulo="Motion graphics para logos", categoria="design",
                resumo="Animar logos com motion graphics. Segunda frase.", tags=["motion-graphics"])
    worker.achar_relacionadas(s, novo)
    assert novo.relacionadas and novo.relacionadas[0].startswith("- [[")
    assert "parecida com: x - " in worker.resposta(novo)
    sem_ia = Meta(url="p", plataforma="x", titulo="T")
    worker.achar_relacionadas(s, sem_ia)
    assert sem_ia.relacionadas == []
