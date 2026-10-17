import json
from types import SimpleNamespace

import httpx
import pytest

from kora import worker
from kora.classificar import classificar
from kora.config import Settings
from kora.db import CONCLUIDO, Queue
from kora.extractors.meta import Meta
from kora.llm import build_provider
from kora.llm.anthropic_provider import AnthropicProvider
from kora.llm.base import Provider, ProviderError
from kora.llm.deepseek import DeepSeekProvider
from kora.llm.ollama import OllamaProvider
from kora.llm.prompt import system_prompt, user_prompt
from kora.llm.schema import SCHEMA, Classificacao, parse
from helpers import BOM, Fake
from kora.vault import destino, render, tags_existentes

# --- schema / parse ---------------------------------------------------------

def test_classificacao_normalizes():
    c = Classificacao(**BOM)
    assert c.titulo == "Motion com Claude" and c.categoria == "design"
    assert c.pontos_chave == ["a", "b"] and c.tags == ["motion-graphics", "claude"]


def test_unknown_category_becomes_outros_and_empty_summary_rejected():
    assert Classificacao(**{**BOM, "categoria": "astrologia"}).categoria == "outros"
    with pytest.raises(ValueError):
        Classificacao(**{**BOM, "resumo": "  "})


def test_parse_accepts_code_fence():
    assert parse("```json\n" + json.dumps(BOM) + "\n```").categoria == "design"
    with pytest.raises(ValueError):
        parse("não é json")


def test_schema_enum_matches_taxonomy():
    assert "outros" in SCHEMA["properties"]["categoria"]["enum"] and SCHEMA["additionalProperties"] is False


# --- providers --------------------------------------------------------------

def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_deepseek_request_and_response():
    seen = {}

    def handler(req):
        seen["req"] = req
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"a":1}'}}]})

    p = DeepSeekProvider("k", "deepseek-flash", "https://api.deepseek.com/", 5, client=mock_client(handler))
    assert p.complete("sys", "usr", SCHEMA) == '{"a":1}'
    body = json.loads(seen["req"].content)
    assert seen["req"].url.path == "/chat/completions" and seen["req"].headers["authorization"] == "Bearer k"
    assert body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize("payload", [
    {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
    {"choices": [{"finish_reason": "length", "message": {"content": "{"}}]},
])
def test_deepseek_empty_or_truncated_is_provider_error(payload):
    p = DeepSeekProvider("k", "m", "http://x", 5, client=mock_client(lambda r: httpx.Response(200, json=payload)))
    with pytest.raises(ProviderError):
        p.complete("s", "u", SCHEMA)


def test_deepseek_http_error_propagates():
    p = DeepSeekProvider("k", "m", "http://x", 5, client=mock_client(lambda r: httpx.Response(401, json={})))
    with pytest.raises(httpx.HTTPStatusError):
        p.complete("s", "u", SCHEMA)


def test_ollama_request_and_response():
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"message": {"content": '{"a":1}'}, "done": True, "done_reason": "stop"})

    p = OllamaProvider("gemma4", "http://localhost:11434/", 5, client=mock_client(handler))
    assert p.complete("sys", "usr", SCHEMA) == '{"a":1}'
    body = seen["body"]
    assert body["stream"] is False and body["format"] == SCHEMA and body["think"] is False
    assert body["options"]["num_ctx"] >= 8192


def test_ollama_empty_is_provider_error():
    p = OllamaProvider("m", "http://x", 5, client=mock_client(
        lambda r: httpx.Response(200, json={"message": {"content": ""}, "done_reason": "stop"})))
    with pytest.raises(ProviderError):
        p.complete("s", "u", SCHEMA)


class FakeAnthropic:
    def __init__(self, content, stop_reason="end_turn"):
        self.kwargs = None
        self.messages = SimpleNamespace(create=self._create)
        self._resp = SimpleNamespace(content=content, stop_reason=stop_reason)

    def _create(self, **kwargs):
        self.kwargs = kwargs
        return self._resp


def test_anthropic_uses_structured_output():
    fake = FakeAnthropic([SimpleNamespace(type="text", text='{"a":1}')])
    p = AnthropicProvider("k", "claude-haiku-5-5", 5, client=fake)
    assert p.complete("sys", "usr", SCHEMA) == '{"a":1}'
    kw = fake.kwargs
    assert kw["model"] == "claude-haiku-5-5" and kw["system"] == "sys"
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert "temperature" not in kw


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_anthropic_refusal_and_truncation_are_provider_errors(stop):
    p = AnthropicProvider("k", "m", 5, client=FakeAnthropic([SimpleNamespace(type="text", text="{}")], stop))
    with pytest.raises(ProviderError):
        p.complete("s", "u", SCHEMA)


# --- factory ----------------------------------------------------------------

def settings(tmp_path, **kw):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                    db_path=tmp_path / "q.sqlite", _env_file=None, **kw)


def test_factory_builds_only_the_chosen_provider(tmp_path):
    keys = dict(anthropic_api_key="a", deepseek_api_key="d")
    for nome, cls in (("anthropic", AnthropicProvider), ("deepseek", DeepSeekProvider), ("ollama", OllamaProvider)):
        provider = build_provider(settings(tmp_path, llm_provider=nome, **keys))
        assert type(provider) is cls and provider.name == nome
    assert build_provider(settings(tmp_path, llm_provider=" Ollama ")).name == "ollama"
    assert build_provider(settings(tmp_path)) is None


def test_factory_fails_at_startup_on_bad_config(tmp_path):
    with pytest.raises(ValueError, match="gemini"):
        build_provider(settings(tmp_path, llm_provider="gemini"))
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_provider(settings(tmp_path, llm_provider="anthropic"))
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_provider(settings(tmp_path, llm_provider="deepseek"))


# --- prompt / classificar ---------------------------------------------------

def test_prompts_include_taxonomy_tags_and_truncate():
    sp = system_prompt(["claude", "github"])
    assert "design:" in sp and "claude, github" in sp and "ferramenta" in sp and "JSON" in sp
    meta = Meta(url="u", plataforma="x", titulo="T", descricao="d" * 5000, conteudo="c" * 50000, conteudo_tipo="transcricao")
    up = user_prompt(meta, 1000)
    assert "<conteudo>" in up and "Transcrição do áudio" in up and len(up) < 2500 and "[…]" in up


def test_classificar_fills_meta_or_leaves_pending(tmp_path):
    s = settings(tmp_path)
    meta = Meta(url="u", plataforma="x", titulo="orig", descricao="d")
    assert classificar(meta, Fake("a", json.dumps(BOM)), s, []) is True
    assert (meta.categoria, meta.ia, meta.titulo) == ("design", "a/m", "Motion com Claude")
    pend = Meta(url="u", plataforma="x", titulo="orig")
    assert classificar(pend, Fake("a", erro=RuntimeError("x")), s, []) is False  # provedor fora do ar
    assert classificar(pend, Fake("a", "lixo"), s, []) is False  # JSON inválido
    assert classificar(pend, None, s, []) is False  # IA desligada
    assert pend.categoria == "" and pend.titulo == "orig"


# --- nota / vault -----------------------------------------------------------

def classificada():
    m = Meta(url="https://u", plataforma="x", titulo="T", descricao="legenda")
    c = Classificacao(**BOM)
    m.titulo, m.resumo, m.pontos_chave, m.categoria, m.tags, m.ia = c.titulo, c.resumo, c.pontos_chave, c.categoria, c.tags, "a/m"
    return m


def test_render_processed_note():
    out = render(classificada(), "2026-10-17")
    assert "categoria: design\ntags: [motion-graphics, claude]\nstatus: processado\nia: \"a/m\"\n---" in out
    assert "## Resumo\nResumo.\nSegunda linha.\n\n## Pontos-chave\n- a\n- b\n\n## Legenda original" in out


def test_render_pending_note_has_no_summary():
    out = render(Meta(url="u", plataforma="x", titulo="T"), "2026-10-17")
    assert "status: pendente" in out and "tags: []" in out and "categoria" not in out and "## Resumo" not in out


def test_destino_and_tags_existentes(tmp_path):
    s = settings(tmp_path)
    assert destino(s, classificada()) == s.saved_dir / "design"
    assert destino(s, Meta(url="u", plataforma="x", titulo="T")) == s.inbox_dir
    for nome, tags in (("a", "claude, motion"), ("b", "claude"), ("c", "")):
        d = s.saved_dir / "design"; d.mkdir(parents=True, exist_ok=True)
        (d / f"{nome}.md").write_text(f"---\ntags: [{tags}]\n---\n# x\n", encoding="utf-8")
    (s.saved_dir / "sem-frontmatter.md").write_text("# x", encoding="utf-8")
    assert tags_existentes(s.saved_dir) == ["claude", "motion"]
    assert tags_existentes(tmp_path / "nao-existe") == []


# --- worker de ponta a ponta ------------------------------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    s = settings(tmp_path)
    sent = []
    monkeypatch.setattr(worker, "send_message", lambda token, chat, text, reply: sent.append(text))
    monkeypatch.setattr(worker, "fetch_meta", lambda url, plat: Meta(url=url, plataforma=plat, titulo="orig", descricao="d"))
    q = Queue(s.db_path)
    q.enqueue("https://x.com/a/status/1", "https://x.com/a/status/1", "x", chat_id=1, message_id=5)
    yield q, s, sent
    q.close()


def test_worker_moves_note_to_category_and_replies(env):
    q, s, sent = env
    assert worker.run_once(q, s, Fake("a", json.dumps(BOM)))
    item = q.get(1)
    assert item.status == CONCLUIDO and item.nota_path.startswith(str(s.saved_dir / "design"))
    assert sent == ["salvo em design: Motion com Claude\nResumo."]


def test_worker_without_ai_keeps_note_pending_in_inbox(env):
    q, s, sent = env
    assert worker.run_once(q, s, Fake("a", erro=RuntimeError("fora")))
    item = q.get(1)
    assert item.status == CONCLUIDO and item.nota_path.startswith(str(s.inbox_dir))
    assert sent == ["salvo (sem IA): orig"]


def test_primeira_frase_cuts_at_sentence_or_word():
    assert worker.primeira_frase("Uma frase. Outra frase.\nTerceira.") == "Uma frase."
    longa = "palavra " * 60
    cortada = worker.primeira_frase(longa, 50)
    assert cortada.endswith("palavra…") and len(cortada) <= 51
