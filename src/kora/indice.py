from .config import Settings

NOME = "Salvos.md"

TEMPLATE = """---
tipo: nota
tags: [moc]
---

# Salvos

Links salvos pelo Kora (bot do Telegram). Este arquivo é criado uma única vez e pode ser editado à vontade.

## Recentes
```dataview
TABLE WITHOUT ID file.link AS Nota, categoria AS Categoria, plataforma AS Plataforma, autor AS Autor, criado AS Salvo
FROM "{pasta}"
WHERE tipo = "link"
SORT criado DESC, file.ctime DESC
LIMIT 30
```

## Por categoria
```dataview
TABLE WITHOUT ID grupo AS Categoria, length(rows) AS Notas, rows.file.link AS Itens
FROM "{pasta}"
WHERE tipo = "link"
GROUP BY default(categoria, "sem categoria") AS grupo
SORT length(rows) DESC
```

## Por plataforma
```dataview
TABLE WITHOUT ID plataforma AS Plataforma, length(rows) AS Notas
FROM "{pasta}"
WHERE tipo = "link"
GROUP BY plataforma
SORT length(rows) DESC
```

## Por tag
```dataview
TABLE WITHOUT ID tag AS Tag, length(rows) AS Notas
FROM "{pasta}"
WHERE tipo = "link"
FLATTEN tags AS tag
GROUP BY tag
SORT length(rows) DESC
LIMIT 30
```

## Por mês
```dataview
TABLE WITHOUT ID mes AS Mês, length(rows) AS Notas
FROM "{pasta}"
WHERE tipo = "link"
GROUP BY dateformat(criado, "yyyy-MM") AS mes
SORT mes DESC
```

## Pendentes de IA
Notas sem categoria ou sem resumo; veja `kora-reclassify` no README do projeto.
```dataview
LIST
FROM "{pasta}"
WHERE tipo = "link" AND status = "pendente"
SORT criado DESC
```
"""


def garantir_indice(settings: Settings) -> bool:
    """Cria Salvos.md se não existir (nunca sobrescreve edições). True se criou."""
    caminho = settings.saved_dir / NOME
    if caminho.exists():
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(TEMPLATE.format(pasta=settings.vault_saved_dir), encoding="utf-8")
    return True
