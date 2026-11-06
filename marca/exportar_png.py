"""Gera PNGs, favicon.ico e ícones de PWA a partir dos SVGs de marca/. Uso: uv run --no-project --with cairosvg --with pillow python3 exportar_png.py"""
import cairosvg, io
from PIL import Image
def png(svg, saida, largura):
    cairosvg.svg2png(url=svg, write_to=saida, output_width=largura)
for nome in ("simbolo-cor", "simbolo-tinta", "icone-app"):
    png(f"{nome}.svg", f"png/{nome}-1024.png", 1024)
for nome in ("palavra-cor", "palavra-tinta", "palavra-branca"):
    png(f"{nome}.svg", f"png/{nome}-1200.png", 1200)
for t in (16, 32, 48, 180, 192, 512):
    png("favicon.svg" if t <= 48 else "icone-app.svg", f"web/icon-{t}.png", t)
imgs = [Image.open(f"web/icon-{t}.png").convert("RGBA") for t in (16, 32, 48)]
imgs[2].save("web/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=imgs[:2])
open("web/site.webmanifest", "w").write('''{
  "name": "Kora", "short_name": "Kora", "start_url": "/", "display": "standalone",
  "background_color": "#070a1c", "theme_color": "#070a1c",
  "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]
}
''')
