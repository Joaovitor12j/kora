"""Mede faster-whisper num áudio. Uso: .venv/bin/python bench_whisper.py audio.m4a [pt]"""
import sys, time
from faster_whisper import WhisperModel

path, lang = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "pt")
for device, ctype in (("cuda", "float16"), ("cpu", "int8")):
    for size in ("small", "medium"):
        try:
            t0 = time.time(); m = WhisperModel(size, device=device, compute_type=ctype)
            load = time.time() - t0; t0 = time.time()
            segs, info = m.transcribe(path, language=lang)
            text = " ".join(s.text for s in segs)
            print(f"{device}/{size}: carga {load:.1f}s, transcrição {time.time()-t0:.1f}s "
                  f"(áudio {info.duration:.0f}s), {len(text)} chars\n  {text[:150]}")
        except Exception as e:
            print(f"{device}/{size}: falhou — {str(e)[:100]}")
