import httpx

from .base import Provider, ProviderError

NUM_CTX = 8192  # o padrão do Ollama (4096) cortaria o prompt em silêncio


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, model: str, base_url: str, timeout: float, client: httpx.Client | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, system: str, user: str, schema: dict) -> str:
        r = self._client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "format": schema,
                "think": False,
                "options": {"temperature": 0.2, "num_ctx": NUM_CTX},
            },
        )
        r.raise_for_status()
        data = r.json()
        if data.get("done_reason") == "length":
            raise ProviderError("resposta truncada")
        texto = (data.get("message", {}).get("content") or "").strip()
        if not texto:
            raise ProviderError("conteúdo vazio")
        return texto
