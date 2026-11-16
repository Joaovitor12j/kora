"""OCR local das imagens de um post (RapidOCR sobre onnxruntime, na CPU)."""
import io
from pathlib import Path

from PIL import Image

_engine = None


def _motor():
    global _engine
    if _engine is None:  # os modelos carregam na primeira chamada
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ler(caminho: Path) -> str:
    resultado, _ = _motor()(str(caminho))
    return "\n".join(linha[1] for linha in resultado or []).strip()


def reduzir(caminho: Path, lado: int = 1024) -> bytes:
    """JPEG com no máximo `lado` px, para mandar a um modelo de visão."""
    with Image.open(caminho) as img:
        img = img.convert("RGB")
        img.thumbnail((lado, lado))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
    return buf.getvalue()
