from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


@lru_cache(maxsize=1)
def _model(name: str) -> WhisperModel:
    return WhisperModel(name, device="cpu", compute_type="int8")


def transcribe(audio: Path, model: str = "small", language: str = "") -> str:
    """Um segmento por linha. Idioma vazio = detecção automática."""
    segments, _ = _model(model).transcribe(str(audio), language=language or None, vad_filter=True)
    return "\n".join(t for s in segments if (t := s.text.strip()))
