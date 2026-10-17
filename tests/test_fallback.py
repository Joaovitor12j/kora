from kora.extractors.fallback import og, parse_instagram
from kora.extractors.meta import _titulo

PAGE = (
    '<meta property="og:title" content="Fernando Rank on Instagram: &quot;Agora voc&#xea; pode&quot;" />'
    '<meta property="og:description" content="1,613 likes - ofernandorank on October 9, 2026: &quot;Agora voc&#xea; pode&quot;." />'
)


def test_og_unescapes():
    assert og(PAGE, "title") == 'Fernando Rank on Instagram: "Agora você pode"'
    assert og(PAGE, "image") == ""


def test_parse_instagram():
    assert parse_instagram(og(PAGE, "title"), og(PAGE, "description")) == ("Fernando Rank", "Agora você pode")


def test_parse_instagram_falls_back_to_description():
    autor, legenda = parse_instagram("Alguém on Instagram", 'x - y on Oct 9: "texto"')
    assert (autor, legenda) == ("Alguém", "texto")


def test_titulo_generic_uses_caption():
    assert _titulo("Video by fulano", "Primeira linha\nsegunda", "u") == "Primeira linha"
    assert _titulo("Título real", "x", "u") == "Título real"
    assert _titulo(None, "", "https://u") == "https://u"
