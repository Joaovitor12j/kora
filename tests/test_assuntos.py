import json

from helpers import BOM, Fake
from kora.assuntos import atribuir, pendentes_de_assunto
from kora.config import Settings
from kora.extractors.meta import Meta
from kora.llm.prompt import system_prompt
from kora.llm.schema import Classificacao
from kora.taxonomia import normalizar_assunto
from kora.vault import ler_nota, mover_categoria, write_note


def cfg(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                    db_path=tmp_path / "q.sqlite", _env_file=None)


def nota_pronta(s, assunto="", categoria="design", titulo="Motion com Claude"):
    m = Meta(url=f"u/{titulo}", plataforma="x", titulo=titulo, categoria=categoria, assunto=assunto,
             resumo="Resumo.", pontos_chave=["a"], tags=["claude"], ia="a/m")
    return write_note(s.saved_dir / categoria, m, 1)


def test_assunto_so_vale_na_categoria_certa():
    assert normalizar_assunto("design", " Motion ") == "motion"
    assert normalizar_assunto("design", "carreira") == ""  # é de negócios
    assert normalizar_assunto("IA", "motion") == ""  # categoria sem assuntos


def test_classificacao_descarta_assunto_invalido():
    assert Classificacao(**{**BOM, "assunto": "motion"}).assunto == "motion"
    assert Classificacao(**{**BOM, "assunto": "xyz"}).assunto == ""
    assert Classificacao(**BOM).assunto == ""  # campo opcional
    assert Classificacao(**{**BOM, "categoria": "IA", "assunto": "motion"}).assunto == ""


def test_prompt_lista_assuntos():
    assert "se categoria for design" in system_prompt([]) and "ui-ux" in system_prompt([])


def test_assunto_vai_e_volta_da_nota(tmp_path):
    s = cfg(tmp_path)
    lida, _ = ler_nota(nota_pronta(s, "motion"))
    assert lida.assunto == "motion"


def test_mover_categoria_apaga_assunto_antigo(tmp_path):
    s = cfg(tmp_path)
    novo = mover_categoria(s, nota_pronta(s, "motion"), "IA")
    assert "assunto:" not in novo.read_text(encoding="utf-8") and "tags: [claude]" in novo.read_text(encoding="utf-8")


def test_atribuir_simula_e_grava(tmp_path):
    s = cfg(tmp_path)
    alvo = nota_pronta(s)
    nota_pronta(s, "video", titulo="Ja tem")
    nota_pronta(s, categoria="IA", titulo="Sem subdivisao")
    assert [n.name for n, _ in pendentes_de_assunto(s)] == [alvo.name]
    ia = Fake("a", json.dumps({"assunto": "motion"}))
    assert atribuir(s, ia, aplicar=False) == (1, 0) and "assunto:" not in alvo.read_text(encoding="utf-8")
    assert atribuir(s, ia, aplicar=True) == (1, 0)
    assert ler_nota(alvo)[0].assunto == "motion" and list(pendentes_de_assunto(s)) == []
    assert atribuir(s, Fake("a", json.dumps({"assunto": "lixo"})), True) == (0, 0)  # nada pendente
