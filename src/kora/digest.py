"""Resumo semanal do acervo: o que entrou, o que ficou fraco e o que vale revisitar.

Grava `Digest/AAAA-Www.md` ao lado dos salvos e, com --enviar, manda o resumo curto ao Telegram.

Uso: uv run kora-digest [--dias 7] [--enviar] [--sem-nota]
"""
import argparse
import datetime as dt
import logging
from collections import Counter
from pathlib import Path

from .config import Settings, get_settings
from .extractors.meta import Meta
from .relacionadas import carregar
from .telegram_api import send_message

log = logging.getLogger("kora.digest")
PASTA = "Digest"
DIAS_PARA_REVISITAR = 30
MAX_REVISITAR = 5


def semana_iso(dia: dt.date) -> str:
    ano, semana, _ = dia.isocalendar()
    return f"{ano}-W{semana:02d}"


def _dia(meta: Meta) -> dt.date | None:
    try:
        return dt.date.fromisoformat(meta.criado)
    except ValueError:
        return None


def revisitar(acervo: list[tuple[Path, Meta]], hoje: dt.date, quantas: int = MAX_REVISITAR) -> list[tuple[Path, Meta]]:
    """Notas com 30+ dias, resumo de verdade e mais ligações a outras (as centrais do acervo).

    O desempate gira com a semana, para não mostrar sempre as mesmas.
    """
    velhas = [(n, m) for n, m in acervo
              if not m.pobre and (d := _dia(m)) and (hoje - d).days >= DIAS_PARA_REVISITAR]
    giro = hoje.isocalendar()[1]
    velhas.sort(key=lambda nm: (-len(nm[1].relacionadas), (int(nm[1].id[1:], 16) + giro) % 997))
    return [nm for nm in velhas if nm[1].relacionadas][:quantas]


def montar(acervo: list[tuple[Path, Meta]], pendentes: int, hoje: dt.date, dias: int = 7) -> dict:
    desde = hoje - dt.timedelta(days=dias)
    novas = sorted(((n, m) for n, m in acervo if (d := _dia(m)) and desde < d <= hoje),
                   key=lambda nm: nm[1].criado, reverse=True)
    temas = Counter(f"{m.categoria}/{m.assunto}" if m.assunto else m.categoria for _, m in novas)
    ferr = Counter(f["nome"] for _, m in novas for f in m.ferramentas)
    return {
        "novas": novas, "temas": temas.most_common(), "ferramentas": ferr.most_common(5),
        "fracas": [(n, m) for n, m in novas if m.pobre], "pendentes": pendentes,
        "revisitar": revisitar(acervo, hoje), "total": len(acervo), "dias": dias,
    }


def texto_nota(d: dict, hoje: dt.date) -> str:
    sem = semana_iso(hoje)
    linhas = [f"---\ncriado: {hoje.isoformat()}\ntipo: nota\ntags: [digest, kora]\n---\n", f"# Digest {sem}\n",
              f"{len(d['novas'])} salvo(s) nos últimos {d['dias']} dias; acervo com {d['total']}.\n"]
    if d["temas"]:
        linhas += ["## Por tema", *[f"- {t}: {n}" for t, n in d["temas"]], ""]
    if d["novas"]:
        linhas += ["## Novos", *[f"- [[{n.stem}]]" for n, _ in d["novas"]], ""]
    if d["ferramentas"]:
        linhas += ["## Ferramentas mais citadas", *[f"- {nome} ({n})" for nome, n in d["ferramentas"]], ""]
    if d["fracas"]:
        linhas += ["## Para revisar (pouco conteúdo)", *[f"- [[{n.stem}]]" for n, _ in d["fracas"]], ""]
    if d["pendentes"]:
        linhas += [f"## Pendentes de IA\n{d['pendentes']} nota(s); rode `kora-reclassify`.\n"]
    if d["revisitar"]:
        linhas += ["## Para revisitar", *[f"- [[{n.stem}]]" for n, _ in d["revisitar"]], ""]
    return "\n".join(linhas)


def texto_telegram(d: dict, hoje: dt.date) -> str:
    partes = [f"Digest da semana {semana_iso(hoje)}: {len(d['novas'])} salvo(s), acervo com {d['total']}."]
    if d["temas"]:
        partes.append("Temas: " + ", ".join(f"{t} ({n})" for t, n in d["temas"][:4]))
    if d["ferramentas"]:
        partes.append("Ferramentas: " + ", ".join(nome for nome, _ in d["ferramentas"][:3]))
    if d["fracas"]:
        partes.append(f"{len(d['fracas'])} com pouco conteúdo para revisar.")
    if d["pendentes"]:
        partes.append(f"{d['pendentes']} pendente(s) de IA.")
    if d["revisitar"]:
        partes.append("Para revisitar: " + "; ".join(m.titulo for _, m in d["revisitar"][:3]))
    return "\n".join(partes)


def pendentes(settings: Settings) -> int:
    from .reclassificar import pendentes as lista
    return len(lista(settings))


def gerar(settings: Settings, hoje: dt.date, dias: int = 7, gravar: bool = True) -> tuple[dict, Path | None]:
    d = montar(carregar(settings.saved_dir), pendentes(settings), hoje, dias)
    caminho = None
    if gravar:
        caminho = settings.saved_dir / PASTA / f"{semana_iso(hoje)}.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto_nota(d, hoje), encoding="utf-8")
    return d, caminho


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--enviar", action="store_true", help="manda o resumo ao Telegram")
    ap.add_argument("--sem-nota", action="store_true", help="não grava a nota no vault")
    args = ap.parse_args()
    settings = get_settings()
    hoje = dt.date.today()
    d, caminho = gerar(settings, hoje, args.dias, gravar=not args.sem_nota)
    texto = texto_telegram(d, hoje)
    print(texto)
    if caminho:
        print(f"nota: {caminho}")
    if args.enviar:
        send_message(settings.telegram_bot_token, settings.telegram_allowed_chat_id, texto)


if __name__ == "__main__":
    main()
