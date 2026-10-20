import json
import os
import re
import stat
from datetime import date

import pytest
from starlette.testclient import TestClient

from kora import taxonomia
from kora.config import get_settings
from kora.db import Queue
from kora.extractors.meta import Meta
from kora.vault import write_note
from kora.web import acervo, ajustes
from kora.web.app import app
from kora.web.sigilos import SIGILOS, chave_do_sigilo

JSON = {"Content-Type": "application/json"}


def nota(settings, titulo, categoria, tags=(), plataforma="x", criado="2026-10-17", resumo="Resumo da nota.", url=None):
    meta = Meta(url=url or f"https://x.com/u/status/{abs(hash(titulo))}", plataforma=plataforma, titulo=titulo,
                autor="Ana", resumo=resumo, pontos_chave=["um", "dois"], categoria=categoria, tags=list(tags),
                ia="fake/m", criado=criado, descricao="Legenda original aqui.")
    pasta = settings.saved_dir / (categoria or "_inbox")
    return write_note(pasta, meta, 1)


@pytest.fixture
def s(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "1")
    monkeypatch.setenv("VAULT_PATH", str(tmp_path / "vault"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "data/queue.sqlite"))
    monkeypatch.setattr(ajustes, "DROPIN", tmp_path / "timer.d/intervalo.conf")
    monkeypatch.setattr(ajustes, "_sistema", lambda *a: (True, ""))
    get_settings.cache_clear()
    acervo._cache.clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def c(s):
    return TestClient(app, base_url="http://127.0.0.1:8765")


# --- galeria ----------------------------------------------------------------------------------

def test_galeria_lista_e_filtra(s, c):
    nota(s, "Motion com Claude", "design", ["motion", "claude"])
    nota(s, "Agentes de IA", "IA", ["agentes"], plataforma="instagram")
    corpo = c.get("/").text
    assert "Motion com Claude" in corpo and "Agentes de IA" in corpo and "<strong>2</strong> links salvos" in corpo
    so_design = c.get("/", params={"c": "design"}).text
    assert "Motion com Claude" in so_design and "Agentes de IA" not in so_design
    assert "Agentes de IA" in c.get("/", params={"p": "instagram"}).text
    assert "Motion com Claude" not in c.get("/", params={"t": "agentes"}).text


def test_busca_sem_acento_e_vazia(s, c):
    nota(s, "Receita de pão", "receitas", ["pao"])
    assert "Receita de pão" in c.get("/", params={"q": "receita pao"}).text
    vazio = c.get("/", params={"q": "inexistente"}).text
    assert "Nenhum link com esses filtros" in vazio


def test_galeria_sem_notas_orienta(s, c):
    assert "Nada salvo ainda" in c.get("/").text


def test_nota_fragmento_e_pagina_completa(s, c):
    path = nota(s, "Detalhe", "design", ["a"])
    rel = path.relative_to(s.saved_dir).as_posix()
    frag = c.get("/nota", params={"p": rel}, headers={"X-Fragmento": "1"}).text
    assert "<html" not in frag and "Legenda original" in frag and "Abrir original" in frag
    assert "<dd>17-10-2026</dd>" in frag and "<dd>2026-10-17</dd>" not in frag
    assert "<html" in c.get("/nota", params={"p": rel}).text


def test_nota_nao_sai_da_pasta_de_salvos(s, c):
    nota(s, "Detalhe", "design")
    (s.vault_path / "segredo.md").write_text("tipo: link", encoding="utf-8")
    for rel in ("../../segredo.md", "/etc/passwd", "design/nao-existe.md"):
        assert c.get("/nota", params={"p": rel}).status_code == 404


def test_url_perigosa_nao_vira_link(s, c):
    path = nota(s, "Xss", "design", url="javascript:alert(1)")
    rel = path.relative_to(s.saved_dir).as_posix()
    assert 'href="javascript:' not in c.get("/nota", params={"p": rel}, headers={"X-Fragmento": "1"}).text


def test_mover_categoria_atualiza_arquivo_e_fila(s, c):
    path = nota(s, "Mover", "design", url="https://x.com/u/status/9")
    q = Queue(s.db_path)
    item, _ = q.enqueue("https://x.com/u/status/9", "https://x.com/u/status/9", "x")
    q.done(item.id, "Mover", str(path))
    rel = path.relative_to(s.saved_dir).as_posix()
    r = c.post("/api/categoria", json={"p": rel, "categoria": "IA"})
    assert r.status_code == 200 and r.json()["categoria"] == "IA"
    assert not path.exists() and (s.saved_dir / r.json()["p"]).exists()
    assert q.get(item.id).nota_path.endswith("/IA/" + path.name)
    q.close()


def test_mover_categoria_invalida(s, c):
    path = nota(s, "Mover", "design")
    rel = path.relative_to(s.saved_dir).as_posix()
    assert c.post("/api/categoria", json={"p": rel, "categoria": "inventada"}).status_code == 400
    assert c.post("/api/categoria", json={"p": "../x.md", "categoria": "IA"}).status_code == 404


def test_pendente_aparece_como_sem_categoria(s, c):
    meta = Meta(url="https://x.com/u/status/1", plataforma="x", titulo="Sem IA")
    write_note(s.inbox_dir, meta, 1)
    corpo = c.get("/").text
    assert "aguardando IA" in corpo and "Sem categoria" in corpo
    assert "Sem IA" in c.get("/", params={"pend": "1"}).text


def test_agrupar_por_dia_e_rotulos():
    hoje = date(2026, 10, 17)
    assert acervo.rotulo_dia("2026-10-17", hoje) == "hoje"
    assert acervo.rotulo_dia("2026-10-16", hoje) == "ontem"
    assert acervo.rotulo_dia("2026-03-02", hoje) == "02-03-2026"
    assert acervo.rotulo_dia("2025-12-31", hoje) == "31-12-2025"
    assert acervo.data_br("2026-10-17") == "17-10-2026" and acervo.data_br("sem data") == "sem data"


def test_sigilo_estavel_para_categoria_nova():
    assert chave_do_sigilo("design") == "espiral" and chave_do_sigilo("") == "marca"
    assert chave_do_sigilo("viagens") == chave_do_sigilo("Viagens") in SIGILOS


# --- segurança ----------------------------------------------------------------------------------

def test_host_de_fora_e_recusado(s):
    assert TestClient(app, base_url="http://evil.example").get("/").status_code == 403


def test_escrita_exige_json_e_origem_local(s, c):
    assert c.post("/api/lote", content=b"x=1", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 403
    assert c.post("/api/lote", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/lote", json={}, headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200


# --- ajustes ------------------------------------------------------------------------------------

def test_env_preserva_comentarios_e_permissao(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# chaves\nLLM_PROVIDER=\nOUTRA=1\n", encoding="utf-8")
    os.chmod(env, 0o600)
    ajustes.gravar_env({"LLM_PROVIDER": "ollama", "OLLAMA_MODEL": "gemma4"}, env)
    assert env.read_text(encoding="utf-8") == "# chaves\nLLM_PROVIDER=ollama\nOUTRA=1\nOLLAMA_MODEL=gemma4\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert ajustes.ler_env(env)["LLM_PROVIDER"] == "ollama"


def test_validar_ajustes():
    assert ajustes.validar({"ANTHROPIC_API_KEY": "", "MAX_AUDIO_MINUTES": "45"}) == {"MAX_AUDIO_MINUTES": "45"}
    for ruim in ({"LLM_PROVIDER": "gpt"}, {"MAX_AUDIO_MINUTES": "0"}, {"LLM_MAX_CHARS": "abc"}, {"HOME": "x"},
                 {"OLLAMA_BASE_URL": "ftp://x"}, {"OLLAMA_MODEL": "a\nOUTRA=1"}, {"WHISPER_MODEL": "enorme"}):
        with pytest.raises(ajustes.ErroDeAjuste):
            ajustes.validar(ruim)


def test_categorias_validas_e_fallback_sempre_no_fim():
    cats = ajustes.validar_categorias([{"nome": "viagens", "descricao": "roteiros"},
                                        {"nome": "IA", "descricao": "modelos"}])
    assert list(cats) == ["viagens", "IA", "outros"]
    for ruim in ([{"nome": "a/b", "descricao": "x"}], [{"nome": "a", "descricao": ""}],
                 [{"nome": "a", "descricao": "x"}, {"nome": "A", "descricao": "y"}], []):
        with pytest.raises(ajustes.ErroDeAjuste):
            ajustes.validar_categorias(ruim)


def test_taxonomia_carrega_arquivo_e_cai_no_padrao(tmp_path):
    arq = tmp_path / "c.json"
    assert taxonomia.carregar(arq) == taxonomia.PADRAO
    arq.write_text("não é json", encoding="utf-8")
    assert taxonomia.carregar(arq) == taxonomia.PADRAO
    taxonomia.salvar({"outros": "resto", "viagens": "roteiros"}, arq)
    assert list(taxonomia.carregar(arq)) == ["viagens", "outros"]


def test_intervalo_roundtrip_e_limites(tmp_path):
    arq = tmp_path / "d/intervalo.conf"
    assert ajustes.ler_intervalo(arq) == ajustes.PADRAO_LOTES
    assert ajustes.gravar_intervalo({"primeiro_min": 30, "intervalo_h": 4}, arq) is True
    assert ajustes.gravar_intervalo({"primeiro_min": 30, "intervalo_h": 4}, arq) is False
    assert ajustes.ler_intervalo(arq) == {"primeiro_min": 30, "intervalo_h": 4}
    assert "OnUnitInactiveSec=\nOnUnitInactiveSec=4h" in arq.read_text(encoding="utf-8")
    for ruim in ((0, 8), (60, 0), (60, 999), ("x", 8)):
        with pytest.raises(ajustes.ErroDeAjuste):
            ajustes.validar_intervalo(*ruim)


def test_salvar_ajustes_grava_tudo_e_nao_devolve_chave(s, c, tmp_path):
    (tmp_path / ".env").write_text("LLM_PROVIDER=\n", encoding="utf-8")
    corpo = {"env": {"LLM_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-segredo", "MAX_AUDIO_MINUTES": "10"},
             "categorias": [{"nome": "viagens", "descricao": "roteiros"}],
             "lotes": {"primeiro_min": 15, "intervalo_h": 2}}
    r = c.put("/api/ajustes", json=corpo)
    assert r.status_code == 200, r.text
    assert "sk-segredo" not in r.text
    assert r.json()["estado"]["chaves"]["DEEPSEEK_API_KEY"] is True
    env = ajustes.ler_env()
    assert env["LLM_PROVIDER"] == "deepseek" and env["DEEPSEEK_API_KEY"] == "sk-segredo"
    assert list(json.loads((tmp_path / "data/categorias.json").read_text(encoding="utf-8"))) == ["viagens", "outros"]
    assert ajustes.ler_intervalo() == {"primeiro_min": 15, "intervalo_h": 2}
    assert [p["nome"] for p in r.json()["passos"]][-2:] == ["Agenda dos lotes atualizada", "Bot reiniciado"]


def test_salvar_ajustes_invalido_nao_grava_nada(s, c, tmp_path):
    r = c.put("/api/ajustes", json={"env": {"MAX_AUDIO_MINUTES": "5"}, "categorias": [{"nome": "a/b", "descricao": "x"}]})
    assert r.status_code == 400 and "pasta" in r.json()["erro"]
    assert not (tmp_path / ".env").exists()


def test_chave_em_branco_mantem_a_salva(s, c, tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-antiga\n", encoding="utf-8")
    c.put("/api/ajustes", json={"env": {"ANTHROPIC_API_KEY": "", "ANTHROPIC_MODEL": "claude-haiku-5-5"}})
    assert ajustes.ler_env()["ANTHROPIC_API_KEY"] == "sk-antiga"


def test_paginas_de_fila_e_ajustes_abrem(s, c):
    assert c.get("/fila").status_code == 200
    corpo = c.get("/ajustes").text
    assert "Inteligência artificial" in corpo and "Sempre existe" in corpo


def test_testar_conexao_sem_provedor(s, c):
    r = c.post("/api/ajustes/testar", json={"provedor": "", "env": {}})
    assert r.json()["ok"] is False


# --- acesso de fora (Tailscale) -----------------------------------------------------------------

from kora.web.app import CABECALHO_USUARIO, decidir_acesso  # noqa: E402

HOST = "kora.rede.ts.net"
EU = "eu@exemplo.com"


def decide(host="localhost", usuario="", metodo="GET", origem=None, tipo="", hosts=frozenset(), usuarios=frozenset()):
    return decidir_acesso(host, usuario, metodo, origem, tipo, set(hosts), set(usuarios))


def test_local_dispensa_login_e_remoto_exige():
    assert decide("127.0.0.1") == (None, False)
    assert decide("::1") == (None, False)
    assert decide(HOST, EU, hosts={HOST}, usuarios={EU}) == (None, True)
    assert decide(HOST, EU, hosts=set(), usuarios={EU})[0] == "Host não permitido"
    assert decide(HOST, "", hosts={HOST}, usuarios={EU})[0] == "Usuário não autorizado"
    assert decide(HOST, "outro@x.com", hosts={HOST}, usuarios={EU})[0] == "Usuário não autorizado"
    assert "WEB_ALLOWED_USERS" in decide(HOST, EU, hosts={HOST})[0]


def test_login_ignora_maiusculas_e_escrita_remota_confere_origem():
    assert decide(HOST, "Eu@Exemplo.com", hosts={HOST}, usuarios={EU})[0] is None
    ok = dict(host=HOST, usuario=EU, metodo="POST", tipo="application/json", hosts={HOST}, usuarios={EU})
    assert decide(**ok, origem=f"https://{HOST}")[0] is None
    assert decide(**ok, origem="https://evil.example")[0] == "Origem não permitida"
    assert decide(**{**ok, "tipo": "text/plain"})[0] == "Envie JSON"


@pytest.fixture
def remoto(s, monkeypatch):
    monkeypatch.setenv("WEB_HOSTS", HOST)
    monkeypatch.setenv("WEB_ALLOWED_USERS", EU)
    get_settings.cache_clear()
    return TestClient(app, base_url=f"https://{HOST}", headers={CABECALHO_USUARIO: EU})


def test_pagina_remota_com_login_certo_mostra_aviso(remoto):
    r = remoto.get("/")
    assert r.status_code == 200 and f"Acesso de fora como {EU}" in r.text


def test_remoto_sem_login_ou_com_login_errado_e_barrado(remoto):
    assert remoto.get("/", headers={CABECALHO_USUARIO: ""}).status_code == 403
    assert remoto.get("/", headers={CABECALHO_USUARIO: "outro@x.com"}).status_code == 403
    r = remoto.get("/api/ollama/modelos", headers={CABECALHO_USUARIO: "outro@x.com"})
    assert r.status_code == 403 and r.json()["erro"] == "Usuário não autorizado"


def test_local_continua_sem_aviso_mesmo_com_acesso_de_fora_ligado(remoto, s):
    local = TestClient(app, base_url="http://127.0.0.1:8765")
    r = local.get("/")
    assert r.status_code == 200 and "Acesso de fora" not in r.text


def test_remoto_nao_muda_quem_entra_mas_salva_o_resto(remoto, tmp_path):
    (tmp_path / ".env").write_text(f"WEB_HOSTS={HOST}\nWEB_ALLOWED_USERS={EU}\n", encoding="utf-8")
    ruim = remoto.put("/api/ajustes", json={"env": {"WEB_ALLOWED_USERS": f"{EU},intruso@x.com"}})
    assert ruim.status_code == 403
    ok = remoto.put("/api/ajustes", json={"env": {"WEB_HOSTS": HOST.upper(), "WEB_ALLOWED_USERS": EU,
                                                  "MAX_AUDIO_MINUTES": "20"}})
    assert ok.status_code == 200, ok.text
    assert ajustes.ler_env()["MAX_AUDIO_MINUTES"] == "20"


def test_local_muda_quem_entra_e_vale_na_hora(s, c, tmp_path):
    (tmp_path / ".env").write_text("", encoding="utf-8")
    assert TestClient(app, base_url=f"https://{HOST}").get("/").status_code == 403
    assert c.put("/api/ajustes", json={"env": {"WEB_HOSTS": HOST, "WEB_ALLOWED_USERS": EU}}).status_code == 200
    r = TestClient(app, base_url=f"https://{HOST}").get("/", headers={CABECALHO_USUARIO: EU})
    assert r.status_code == 200


def test_validar_acesso_de_fora():
    assert ajustes.validar({"WEB_HOSTS": " A.ts.net , b.ts.net ", "WEB_ALLOWED_USERS": "a@x.com, b@y.com"}) == \
        {"WEB_HOSTS": "A.ts.net,b.ts.net", "WEB_ALLOWED_USERS": "a@x.com,b@y.com"}
    for ruim in ({"WEB_HOSTS": "https://a.ts.net"}, {"WEB_HOSTS": "a.ts.net:8765"}, {"WEB_HOSTS": "a b"},
                 {"WEB_ALLOWED_USERS": "sem-arroba"}, {"WEB_ALLOWED_USERS": "a@x.com;b@y.com"}):
        with pytest.raises(ajustes.ErroDeAjuste):
            ajustes.validar(ruim)


def test_tela_de_ajustes_remota_trava_o_acesso(remoto):
    html = remoto.get("/ajustes").text
    assert "abra a Kora pelo próprio computador" in html
    assert re.search(r'name="WEB_HOSTS"[^>]*readonly', html) and re.search(r'name="WEB_ALLOWED_USERS"[^>]*readonly', html)


def test_selo_da_fila_conta_aguardando_e_processando_sem_as_falhas(s, c):
    assert 'class="selo"' not in c.get("/").text  # fila vazia: sem selo
    q = Queue(s.db_path)
    for n in range(1, 5):
        q.enqueue(f"https://x.com/u/status/{n}", f"https://x.com/u/status/{n}", "x")
    q.claim_next()  # um vira "processando"
    falho = q.claim_next()
    q.fail(falho.id, "erro", now=0)
    q.fail(falho.id, "erro", now=0)
    q.fail(falho.id, "erro", now=0)
    contagem = q.counts()
    assert contagem.get("falhou") == 1  # a falha não entra no selo
    esperado = contagem.get("na_fila", 0) + contagem.get("processando", 0)
    q.close()
    html = c.get("/fila").text
    assert f'<span class="selo" aria-hidden="true">{esperado}</span>' in html
    assert f"({esperado} itens)" in html and esperado >= 2


def test_arquivos_estaticos_vao_com_versao_para_nao_ficar_em_cache(s, c):
    html = c.get("/").text
    for arquivo in ("kora.css", "kora.js", "acervo.js"):
        assert re.search(rf'/static/{re.escape(arquivo)}\?v=\d+"', html), arquivo
    assert c.get("/static/kora.css?v=1").status_code == 200


def test_titulo_da_aba_e_sempre_kora(s, c):
    path = nota(s, "Detalhe", "design")
    rel = path.relative_to(s.saved_dir).as_posix()
    for url in ("/", "/fila", "/ajustes", f"/nota?p={rel}", "/nota?p=nao-existe.md"):
        assert "<title>Kora</title>" in c.get(url).text, url
