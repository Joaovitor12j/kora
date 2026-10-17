"""Dublês compartilhados pelos testes."""
from kora.llm.base import Provider

BOM = {"titulo": " Motion com Claude ", "resumo": "Resumo.\nSegunda linha.", "pontos_chave": ["a", " ", "b"],
       "categoria": "DESIGN", "tags": ["#Motion Graphics", "claude", "claude", ""]}


class Fake(Provider):
    def __init__(self, name, resposta=None, erro=None):
        self.name, self.model, self.resposta, self.erro, self.chamadas = name, "m", resposta, erro, 0

    def complete(self, system, user, schema):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return self.resposta
