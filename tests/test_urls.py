import pytest

from kora.urls import canonicalize, extract_urls, needs_resolution, platform_of


def test_extract_urls_trims_punctuation_and_dedupes():
    text = "olha (https://x.com/a/status/1). e https://x.com/a/status/1, mais https://exemplo.com/p?q=1!"
    assert extract_urls(text) == ["https://x.com/a/status/1", "https://exemplo.com/p?q=1"]


def test_extract_urls_none():
    assert extract_urls("sem link aqui") == []


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://www.instagram.com/reel/DejkA_8xi5P/?psln=MzRl&srtk=Mz", "https://www.instagram.com/reel/DejkA_8xi5P/"),
        ("https://instagram.com/p/DeSoJBNoJcI?igsh=abc", "https://www.instagram.com/p/DeSoJBNoJcI/"),
        ("https://www.tiktok.com/@u/video/7675794471078104340?_r=1&_t=ZS-9", "https://www.tiktok.com/@u/video/7675794471078104340"),
        ("https://twitter.com/user/status/123?s=20&t=xyz", "https://x.com/user/status/123"),
        ("https://mobile.twitter.com/user/status/123/", "https://x.com/user/status/123"),
        ("https://youtu.be/jNQXAC9IVRw?si=abc", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
        ("https://www.youtube.com/watch?v=jNQXAC9IVRw&feature=share&t=10", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
        ("https://youtube.com/shorts/abc123?si=z", "https://www.youtube.com/watch?v=abc123"),
        ("https://www.Exemplo.com/artigo/?utm_source=x&b=2&a=1#topo", "https://exemplo.com/artigo?a=1&b=2"),
    ],
)
def test_canonicalize(raw, expected):
    assert canonicalize(raw) == expected


def test_canonicalize_is_idempotent():
    once = canonicalize("https://www.instagram.com/reel/X/?igsh=1")
    assert canonicalize(once) == once


@pytest.mark.parametrize(
    "url, platform",
    [
        ("https://vt.tiktok.com/ZSgj68s1d/", "tiktok"),
        ("https://x.com/a/status/1", "x"),
        ("https://www.instagram.com/p/X/", "instagram"),
        ("https://youtu.be/x", "youtube"),
        ("https://exemplo.com/a", "web"),
    ],
)
def test_platform_of(url, platform):
    assert platform_of(url) == platform


def test_needs_resolution():
    assert needs_resolution("https://vt.tiktok.com/ZSgj68s1d/")
    assert not needs_resolution("https://www.tiktok.com/@u/video/1")
