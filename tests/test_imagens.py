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


# --- guardar imagens como referência ---

def test_quer_imagens():
    from kora.urls import quer_imagens
    assert quer_imagens("https://instagram.com/p/x ref")
    assert quer_imagens("#REF https://instagram.com/p/x")
    assert quer_imagens("imagens: https://instagram.com/p/x")
    assert not quer_imagens("https://instagram.com/p/x")
    assert not quer_imagens("https://site.com/referencia-de-design")  # só conta fora do link
    assert not quer_imagens("olha que referências boas https://x.com/a/status/1".replace("referências", "coisas"))


def test_db_guardar_e_pedir_depois(tmp_path):
    from kora.db import CONCLUIDO, NA_FILA, Queue
    q = Queue(tmp_path / "q.sqlite")
    item, _ = q.enqueue("u", "c", "instagram")
    assert not item.guardar_imagens
    q.done(item.id, "T", "/x.md")
    pedido = q.pedir_imagens(item.id)
    assert pedido.guardar_imagens and pedido.status == NA_FILA
    novo, _ = q.enqueue("u2", "c2", "instagram", guardar_imagens=True)
    assert novo.guardar_imagens
    q.close()


def test_guarda_imagens_com_flag_ou_pouco_texto(settings, monkeypatch):
    monkeypatch.setattr(imagens, "listar", lambda *a: ["u"])
    monkeypatch.setattr(imagens, "baixar", lambda urls, pasta: [foto(pasta / "1.png", "OI")])
    monkeypatch.setattr(ocr, "ler", lambda arquivo: "texto longo " * 20)
    sem = Meta(url="u", plataforma="instagram", titulo="t")
    media.attach_imagens(sem, settings)
    assert sem.imagens_salvar == []  # texto suficiente e sem pedido: descarta
    com = Meta(url="u", plataforma="instagram", titulo="t")
    media.attach_imagens(com, settings, guardar=True)
    assert len(com.imagens_salvar) == 1 and com.imagens_salvar[0][0] == ".png"
    monkeypatch.setattr(ocr, "ler", lambda arquivo: "oi")
    auto = Meta(url="u", plataforma="instagram", titulo="t")
    media.attach_imagens(auto, settings)
    assert len(auto.imagens_salvar) == 1  # pouco texto: a imagem é o conteúdo


def test_nota_embute_imagens_e_ida_e_volta(settings, tmp_path):
    from kora.vault import ler_nota, salvar_imagens, write_note
    meta = Meta(url="https://instagram.com/p/x", plataforma="instagram", titulo="T", categoria="design",
                imagens_salvar=[(".jpg", b"aaa"), (".png", b"bbb")])
    salvar_imagens(settings, meta, 7)
    assert meta.imagens_links == ["Referencias/Salvos/_anexos/7/01.jpg", "Referencias/Salvos/_anexos/7/02.png"]
    assert (settings.vault_path / meta.imagens_links[1]).read_bytes() == b"bbb"
    nota = write_note(settings.saved_dir / "design", meta, 7)
    assert "## Imagens\n![[Referencias/Salvos/_anexos/7/01.jpg]]\n![[Referencias/Salvos/_anexos/7/02.png]]" in nota.read_text(encoding="utf-8")
    assert ler_nota(nota)[0].imagens_links == meta.imagens_links


def test_worker_guarda_imagens_e_refaz_nota(settings, monkeypatch):
    from kora import worker
    from kora.db import Queue
    q = Queue(settings.db_path)
    item, _ = q.enqueue("https://instagram.com/p/x", "https://instagram.com/p/x", "instagram", guardar_imagens=True)
    monkeypatch.setattr(worker, "fetch_meta", lambda url, plat: Meta(url=url, plataforma=plat, titulo="Carrossel"))
    monkeypatch.setattr(imagens, "listar", lambda *a: ["u"])
    monkeypatch.setattr(imagens, "baixar", lambda urls, pasta: [foto(pasta / "1.png", "OI")])
    monkeypatch.setattr(ocr, "ler", lambda arquivo: "slide")
    worker.process(q, settings, item)
    nota = next(settings.inbox_dir.glob("*.md"))
    assert "![[Referencias/Salvos/_anexos/%d/01.png]]" % item.id in nota.read_text(encoding="utf-8")
    # refazer sem baixar de novo: mantém a nota única e as imagens
    monkeypatch.setattr(imagens, "listar", lambda *a: [])
    refeito = q.pedir_imagens(item.id)
    worker.process(q, settings, refeito)
    assert len(list(settings.inbox_dir.glob("*.md"))) == 1
    assert (settings.vault_path / f"Referencias/Salvos/_anexos/{item.id}/01.png").exists()
    q.close()
