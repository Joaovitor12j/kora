from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Falha esperada de um provedor (resposta vazia, truncada, recusa)."""


class Provider(ABC):
    name: str
    model: str
    suporta_visao = False

    @property
    def label(self) -> str:
        return f"{self.name}/{self.model}"

    @abstractmethod
    def complete(self, system: str, user: str, schema: dict, imagens: list[bytes] | None = None) -> str:
        """Devolve o texto da resposta, que deve ser um objeto JSON conforme `schema`.

        `imagens` (JPEG) só é usado por provedores com `suporta_visao`; os outros ignoram.
        """
