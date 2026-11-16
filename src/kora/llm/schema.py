import json
import re

from pydantic import BaseModel, field_validator, model_validator

from ..tags import normalizar_tag
from ..taxonomia import CATEGORIAS, normalizar_assunto, normalizar_categoria

MAX_TAGS = 6
MAX_PONTOS = 8

# JSON Schema enviado aos provedores que o aceitam (Anthropic, Ollama).
SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "resumo": {"type": "string"},
        "pontos_chave": {"type": "array", "items": {"type": "string"}},
        "categoria": {"type": "string", "enum": list(CATEGORIAS)},
        "assunto": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titulo", "resumo", "pontos_chave", "categoria", "tags"],
    "additionalProperties": False,
}


class Classificacao(BaseModel):
    titulo: str
    resumo: str
    pontos_chave: list[str]
    categoria: str
    assunto: str = ""
    tags: list[str]

    @field_validator("titulo", "resumo")
    @classmethod
    def _nao_vazio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("campo vazio")
        return v

    @field_validator("categoria")
    @classmethod
    def _categoria(cls, v: str) -> str:
        return normalizar_categoria(v)  # fora da lista vira "outros"

    @field_validator("pontos_chave")
    @classmethod
    def _pontos(cls, v: list[str]) -> list[str]:
        return [p.strip() for p in v if p.strip()][:MAX_PONTOS]

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(t for t in map(normalizar_tag, v) if t))[:MAX_TAGS]


    @model_validator(mode="after")
    def _assunto(self):
        self.assunto = normalizar_assunto(self.categoria, self.assunto)  # assunto de outra categoria some
        return self


_CERCA = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse(texto: str) -> Classificacao:
    """Aceita JSON puro ou dentro de cerca ```json (modelos locais costumam cercar)."""
    return Classificacao.model_validate(json.loads(_CERCA.sub("", texto.strip())))
