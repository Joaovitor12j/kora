import pytest
from PIL import Image, ImageDraw, ImageFont

from kora import media, ocr
from kora.config import Settings
from kora.extractors import fallback, imagens
from kora.extractors.meta import Meta
from kora.llm.prompt import user_prompt


@pytest.fixture
def settings(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path, _env_file=None)


def foto(caminho, texto):
    img = Image.new("RGB", (900, 300), "white")
    ImageDraw.Draw(img).text((30, 100), texto, fill="black", font=ImageFont.load_default(size=70))
    img.save(caminho)
    return caminho


def test_so_imagens_filtra_e_limita():
    linhas = ["https://a/1.jpg?x=1", "ytdl:https://a/v", "https://a/2.mp4", "https://a/1.jpg?x=1",
              "https://a/3.webp", "lixo", "https://a/4.png"]
    assert imagens.so_imagens(linhas, 3) == ["https://a/1.jpg?x=1", "https://a/3.webp", "https://a/4.png"]


def test_fotos_do_fxtwitter():
    data = {"tweet": {"media": {"photos": [{"url": "https://p/1.jpg"}, {"url": "https://p/2.jpg"}]}}}
    assert fallback.parse_fx_fotos(data) == ["https://p/1.jpg", "https://p/2.jpg"]
    assert fallback.parse_fx_fotos({"tweet": {}}) == []


def test_ocr_le_texto_real(tmp_path):
    assert "CLAUDE" in ocr.ler(foto(tmp_path / "a.png", "CLAUDE CODE")).upper()


def test_attach_imagens_monta_slides(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(imagens, "listar", lambda *a: ["u1", "u2"])
    monkeypatch.setattr(imagens, "baixar", lambda urls, pasta: [foto(pasta / "1.png", "PRIMEIRO"), foto(pasta / "2.png", "SEGUNDO")])
    meta = Meta(url="https://instagram.com/p/x", plataforma="instagram", titulo="t")
    media.attach_imagens(meta, settings)
    assert meta.conteudo_tipo == "imagens"
    assert "[slide 1]" in meta.conteudo and "[slide 2]" in meta.conteudo
    assert "PRIMEIRO" in meta.conteudo.upper()
    assert "Texto lido das imagens" in user_prompt(meta, 1000)
    assert meta.imagens_visao == []  # visão desligada


def test_visao_so_quando_ocr_pouco(settings, monkeypatch):
    settings.imagens_visao = True
    monkeypatch.setattr(imagens, "listar", lambda *a: ["u"])
    monkeypatch.setattr(imagens, "baixar", lambda urls, pasta: [foto(pasta / "1.png", "OI")])
    meta = Meta(url="https://instagram.com/p/x", plataforma="instagram", titulo="t")
    media.attach_imagens(meta, settings)
    assert len(meta.imagens_visao) == 1 and meta.imagens_visao[0][:2] == b"\xff\xd8"


@pytest.mark.parametrize("plat,extra", [("web", {}), ("instagram", {"tem_midia": True}), ("instagram", {"conteudo": "x"})])
def test_nao_age_fora_do_escopo(settings, monkeypatch, plat, extra):
    monkeypatch.setattr(imagens, "listar", lambda *a: pytest.fail("não devia listar"))
    media.attach_imagens(Meta(url="u", plataforma=plat, titulo="t", **extra), settings)


def test_falha_nao_derruba(settings, monkeypatch):
    def boom(*a):
        raise RuntimeError("login")
    monkeypatch.setattr(imagens, "listar", boom)
    meta = Meta(url="u", plataforma="instagram", titulo="t")
    media.attach_imagens(meta, settings)
    assert meta.conteudo == ""


def test_nota_com_texto_das_imagens_vai_e_volta(tmp_path):
    from kora.vault import ler_nota, write_note
    meta = Meta(url="https://instagram.com/p/x", plataforma="instagram", titulo="T", conteudo="[slide 1]\nolá\n\n[slide 2]\nmundo",
                conteudo_tipo="imagens")
    nota = write_note(tmp_path, meta, 1)
    assert "## Texto das imagens" in nota.read_text(encoding="utf-8")
    lido, _ = ler_nota(nota)
    assert lido.conteudo_tipo == "imagens" and "[slide 2]" in lido.conteudo
