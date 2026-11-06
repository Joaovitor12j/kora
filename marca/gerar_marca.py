"""Gera a palavra "kora" da marca Kora como paths (sem fonte). Uso: python3 gerar_marca.py"""
CY, MG, TX, INK = "#3DF0FF", "#F046B4", "#E7ECFF", "#15130F"
H, S, XH = 224, 34, 132            # altura do k, espessura da haste, altura-x
BASE = H
def k(x, c1, c2, gap=9, h=80, w=46, notch=26):
    cy = H / 2; x0 = x + S + gap
    haste = f"M{x} 0H{x+S}V{H}L{x+S/2} {H-notch}L{x} {H}Z"
    chev = f"M{x0} {cy}L{x0+h} {cy-h}H{x0+h+w}L{x0+w} {cy}L{x0+h+w} {cy+h}H{x0+h}Z"
    return f'<path fill="{c1}" d="{haste}"/><path fill="{c2}" d="{chev}"/>', x0 + h + w
def anel(x, r=67):
    cx, cy = x + r, BASE - r + 1
    d = f"M{cx-r} {cy}a{r} {r} 0 1 0 {2*r} 0a{r} {r} 0 1 0 {-2*r} 0ZM{cx-r+S} {cy}a{r-S} {r-S} 0 1 1 {2*(r-S)} 0a{r-S} {r-S} 0 1 1 {-2*(r-S)} 0Z"
    return d, x + 2 * r
def o(x, c):
    d, fim = anel(x); return f'<path fill="{c}" fill-rule="evenodd" d="{d}"/>', fim
def r(x, c, h=44, w=46):
    top = BASE - XH; cy = top + 52
    haste = f"M{x} {top}H{x+S}V{BASE}H{x}Z"
    arm = f"M{x+S} {cy}L{x+S+h} {cy-h}H{x+S+h+w}L{x+S+w} {cy}Z"
    return f'<path fill="{c}" d="{haste}"/><path fill="{c}" d="{arm}"/>', x + S + h + w
def a(x, c):
    d, fim = anel(x)
    top = BASE - XH
    return f'<path fill="{c}" fill-rule="evenodd" d="{d}"/><path fill="{c}" d="M{fim-S} {top}H{fim}V{BASE}H{fim-S}Z"/>', fim
def palavra(c1, c2, ct, gap=26):
    x = 0; partes = []
    p, x = k(x, c1, c2); partes.append(p); x += gap
    p, x = o(x, ct); partes.append(p); x += gap
    p, x = r(x, ct); partes.append(p); x += gap - 6
    p, x = a(x, ct); partes.append(p)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-12 -12 {x+24:.0f} {H+24}"><title>kora</title>{"".join(partes)}</svg>'
for nome, cs in {"palavra-cor": (CY, MG, TX), "palavra-tinta": (INK, INK, INK), "palavra-branca": ("#fff",) * 3}.items():
    open(f"{nome}.svg", "w").write(palavra(*cs))

# ---- símbolo (k) e ícones ----
NOITE = "#070A1C"
def simbolo(stemw=40, gap=10, w=51, h=80, notch=28, c1=CY, c2=MG, escala=1.0, fundo=None):
    sx = 56; x0 = sx + stemw + gap
    total = x0 + h + w - sx; tx = (256 - total) / 2 - sx
    corpo = (f'<path fill="{c1}" d="M{sx} 16H{sx+stemw}V240L{sx+stemw/2} {240-notch}L{sx} 240Z"/>'
             f'<path fill="{c2}" d="M{x0} 128L{x0+h} {128-h}H{x0+h+w}L{x0+w} 128L{x0+h+w} {128+h}H{x0+h}Z"/>')
    g = f'<g transform="translate(128 128) scale({escala}) translate(-128 -128) translate({tx:.1f} 0)">{corpo}</g>'
    bg = f'<rect width="256" height="256" rx="58" fill="{fundo}"/>' if fundo else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><title>Kora</title>{bg}{g}</svg>'
open("simbolo-cor.svg", "w").write(simbolo())
open("simbolo-tinta.svg", "w").write(simbolo(c1=INK, c2=INK))
open("simbolo-pequeno-cor.svg", "w").write(simbolo(stemw=52, gap=8, w=66, h=84, notch=34))
open("icone-app.svg", "w").write(simbolo(escala=.68, fundo=NOITE))
open("favicon.svg", "w").write(simbolo(stemw=52, gap=8, w=66, h=84, notch=34, escala=.8, fundo=NOITE))
