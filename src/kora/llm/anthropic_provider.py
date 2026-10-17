import anthropic

from .base import Provider, ProviderError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float, client: anthropic.Anthropic | None = None):
        self.model = model
        # max_retries baixo: se a Anthropic estiver fora, o orquestrador passa para o próximo.
        self.client = client or anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=1)

    def complete(self, system: str, user: str, schema: dict) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason == "refusal":
            raise ProviderError("modelo recusou a requisição")
        if response.stop_reason == "max_tokens":
            raise ProviderError("resposta truncada (max_tokens)")
        texto = next((b.text for b in response.content if b.type == "text"), "")
        if not texto:
            raise ProviderError("resposta sem texto")
        return texto
