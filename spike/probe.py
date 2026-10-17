"""Fase 0: para cada link, testa metadados (dump-json) e download de áudio.
Uso: .venv/bin/python probe.py [--cookies-from-browser firefox]
Saída: out/<n>/ + resumo em out/resumo.md
"""
import argparse, sys, time
from pathlib import Path
import yt_dlp

ap = argparse.ArgumentParser()
ap.add_argument("--cookies-from-browser")
ap.add_argument("--links", default="links.txt")
a = ap.parse_args()

out = Path("out"); out.mkdir(exist_ok=True)
rows = []
for i, line in enumerate(Path(a.links).read_text().splitlines(), 1):
    url, _, label = line.partition("#")
    url, label = url.strip(), label.strip()
    if not url:
        continue
    d = out / f"{i:02d}"; d.mkdir(exist_ok=True)
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if a.cookies_from_browser:
        opts["cookiesfrombrowser"] = (a.cookies_from_browser,)
    meta = audio = "falhou"; err = ""; t0 = time.time()
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
        meta = f"ok: {info.get('title') or info.get('description','')[:40]!r} / {info.get('uploader')}"
        try:
            with yt_dlp.YoutubeDL({**opts, "skip_download": False, "format": "bestaudio/best",
                                   "outtmpl": str(d / "audio.%(ext)s")}) as y:
                y.download([url])
            audio = "ok" if any(d.glob("audio.*")) else "sem áudio"
        except Exception as e:
            audio = "falhou"; err = str(e)[:120]
    except Exception as e:
        err = str(e)[:120]
    rows.append((i, label, url, meta, audio, f"{time.time()-t0:.0f}s", err))
    print(rows[-1], file=sys.stderr)

ok = sum(r[3].startswith("ok") and r[4] == "ok" for r in rows)
md = ["| # | tipo | metadados | áudio | tempo | erro |", "|---|---|---|---|---|---|"]
md += [f"| {r[0]} | {r[1]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |" for r in rows]
md.append(f"\n**{ok}/{len(rows)} utilizáveis** (critério: ≥ 80%)")
(out / "resumo.md").write_text("\n".join(md))
print("\n".join(md))
