import httpx

from .base import Provider, ProviderError


class DeepSeekProvider(Provider):
    """API compatível com OpenAI. O modo JSON não aceita schema: ele vai descrito no prompt."""

    name = "deepseek"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float,
                 client: httpx.Client | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, system: str, user: str, schema: dict) -> str:
        r = self._client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "thinking": {"type": "disabled"},  # classificar não precisa de raciocínio longo
                "temperature": 0.2,
                "max_tokens": 4096,
            },
        )
        r.raise_for_status()
        choice = r.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ProviderError("resposta truncada (max_tokens)")
        texto = (choice["message"].get("content") or "").strip()
        if not texto:  # a documentação avisa que o modo JSON às vezes devolve vazio
            raise ProviderError("conteúdo vazio")
        return texto
