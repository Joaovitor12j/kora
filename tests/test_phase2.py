import pytest

from kora import media
from kora.config import Settings
from kora.extractors import article, fallback, meta as meta_mod
from kora.extractors.legendas import escolher_url, parse_vtt
from kora.extractors.meta import Meta, fetch_meta
from kora.vault import render

VTT = """WEBVTT
Kind: captions

1
00:00:00.000 --> 00:00:02.000
<c>Olá</c> pessoal

2
00:00:02.000 --> 00:00:04.000
Olá pessoal

NOTE comentário
isso some

00:00:04.000 --> 00:00:06.000
vamos &amp; começar
"""


def test_parse_vtt_strips_tags_ids_and_duplicates():
    assert parse_vtt(VTT) == "Olá pessoal\nvamos &amp; começar"


def test_escolher_url_prefers_pt_then_en_and_vtt_only():
    subs = {
        "fr": [{"ext": "vtt", "url": "fr"}],
        "en": [{"ext": "vtt", "url": "en"}],
        "pt-BR": [{"ext": "json3", "url": "x"}, {"ext": "vtt", "url": "pt"}],
    }
    assert escolher_url(subs) == "pt"
    assert escolher_url({"en": [{"ext": "vtt", "url": "en"}], "fr": []}) == "en"
    assert escolher_url({"fr": [{"ext": "vtt", "url": "fr"}]}) is None
    assert escolher_url({}) is None


def test_parse_fxtwitter():
    data = {"tweet": {"text": "linha um\nlinha dois", "author": {"name": "Ana", "screen_name": "ana"},
                      "created_timestamp": 1760000000}}
    out = fallback.parse_fxtwitter(data)
    assert out["autor"] == "@ana" and out["titulo"] == "Ana: linha um"
    assert out["descricao"] == "linha um\nlinha dois" and out["publicado"] == "2025-10-09"
    with pytest.raises(ValueError):
        fallback.parse_fxtwitter({"tweet": {"text": " "}})


def test_article_parse_and_too_short():
    html = ("<html><head><title>Meu artigo</title></head><body><article><h1>Meu artigo</h1>"
            + "<p>" + "Texto longo sobre filas no Laravel. " * 20 + "</p></article></body></html>")
    out = article.parse(html, "https://exemplo.com/a")
    assert out["conteudo_tipo"] == "artigo" and "filas no Laravel" in out["conteudo"]
    with pytest.raises(ValueError):
        article.parse("<html><body><p>curto</p></body></html>", "https://exemplo.com/b")


def test_web_tries_article_then_falls_back(monkeypatch):
    chamadas = []

    def falha(nome):
        def f(url):
            chamadas.append(nome)
            raise ValueError(nome)
        return f

    monkeypatch.setattr(meta_mod.article, "extract", falha("artigo"))
    monkeypatch.setattr(meta_mod.ytdlp, "extract", falha("ytdlp"))
    monkeypatch.setattr(meta_mod.fallback, "web", lambda url: {"titulo": "Só og", "descricao": "d"})
    m = fetch_meta("https://exemplo.com", "web")
    assert chamadas == ["artigo", "ytdlp"] and m.titulo == "Só og"


def test_fetch_meta_all_sources_fail(monkeypatch):
    monkeypatch.setattr(meta_mod.ytdlp, "extract", lambda u: (_ for _ in ()).throw(ValueError("a")))
    monkeypatch.setattr(meta_mod.fallback, "extract", lambda u, p: (_ for _ in ()).throw(ValueError("b")))
    with pytest.raises(RuntimeError, match="a | b"):
        fetch_meta("https://x.com/a/status/1", "x")


@pytest.fixture
def settings(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path, _env_file=None)


def video(**kw):
    return Meta(url="https://www.tiktok.com/@u/video/1", plataforma="tiktok", titulo="t", tem_midia=True, duracao=60, **kw)


def test_attach_transcript_transcribes_and_cleans_audio(monkeypatch, settings):
    seen = {}

    def fake_download(url, directory):
        f = directory / "audio.mp3"
        f.write_bytes(b"x")
        seen["dir"] = directory
        return f

    monkeypatch.setattr(media.ytdlp, "download_audio", fake_download)
    monkeypatch.setattr(media, "transcribe", lambda audio, model, lang: "olá\nmundo")
    m = video()
    media.attach_transcript(m, settings)
    assert (m.conteudo, m.conteudo_tipo) == ("olá\nmundo", "transcricao")
    assert not seen["dir"].exists()


def test_attach_transcript_prefers_site_subtitles(monkeypatch, settings):
    monkeypatch.setattr(media.legendas, "baixar", lambda subs: "legenda do site")
    monkeypatch.setattr(media.ytdlp, "download_audio", lambda *a: pytest.fail("não deveria baixar áudio"))
    m = video(legendas={"pt": []})
    media.attach_transcript(m, settings)
    assert (m.conteudo, m.conteudo_tipo) == ("legenda do site", "legenda")


def test_attach_transcript_skips_long_and_swallows_errors(monkeypatch, settings):
    monkeypatch.setattr(media.ytdlp, "download_audio", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    longo = video(); longo.duracao = settings.max_audio_minutes * 60 + 1
    media.attach_transcript(longo, settings)
    assert longo.conteudo == ""
    quebra = video()
    media.attach_transcript(quebra, settings)  # não levanta
    assert quebra.conteudo == ""
    texto = Meta(url="u", plataforma="web", titulo="t", conteudo="artigo", conteudo_tipo="artigo", tem_midia=True)
    media.attach_transcript(texto, settings)
    assert texto.conteudo == "artigo"


def test_render_sections():
    base = dict(url="https://u", plataforma="tiktok", titulo="T", descricao="legenda")
    t = render(Meta(**base, conteudo="um\n\ndois", conteudo_tipo="transcricao"), "2026-10-17")
    assert "## Transcrição\n> [!note]- Transcrição completa\n> um\n> dois\n" in t
    s = render(Meta(**base, conteudo="x", conteudo_tipo="legenda"), "2026-10-17")
    assert "> [!note]- Legenda do vídeo" in s
    a = render(Meta(**base, conteudo="corpo", conteudo_tipo="artigo"), "2026-10-17")
    assert "## Conteúdo\ncorpo" in a and "Transcrição" not in a
    assert "##" not in render(Meta(**base), "2026-10-17").split("## Legenda original")[1]


def test_x_long_tweet_uses_full_text(monkeypatch):
    curto = {"titulo": "Autor - cortado ...", "descricao": "texto cor"}
    monkeypatch.setattr(meta_mod.ytdlp, "extract", lambda u: dict(curto, tem_midia=True))
    monkeypatch.setattr(meta_mod.fallback, "x", lambda u: {"titulo": "Autor: inteiro", "descricao": "texto cortado e o resto"})
    m = fetch_meta("https://x.com/a/status/1", "x")
    assert m.descricao == "texto cortado e o resto" and m.titulo == "Autor: inteiro" and m.tem_midia


def test_x_keeps_ytdlp_text_when_fxtwitter_fails_or_shorter(monkeypatch):
    monkeypatch.setattr(meta_mod.ytdlp, "extract", lambda u: {"titulo": "T", "descricao": "texto longo do yt-dlp"})
    monkeypatch.setattr(meta_mod.fallback, "x", lambda u: (_ for _ in ()).throw(ValueError("401")))
    assert fetch_meta("https://x.com/a/status/1", "x").descricao == "texto longo do yt-dlp"
    monkeypatch.setattr(meta_mod.fallback, "x", lambda u: {"titulo": "X", "descricao": "curto"})
    assert fetch_meta("https://x.com/a/status/1", "x").titulo == "T"
