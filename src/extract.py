"""Extração estruturada de achados a partir do texto limpo de uma página.

Usa o Claude Haiku 4.5 com "structured outputs" (output_config.format) para
garantir que a resposta seja sempre um JSON válido no schema esperado — sem
precisar de regex/retry de parsing.

Este módulo é a camada que substitui os parsers CSS/XPath por site: em vez
de codificar regras específicas para o HTML de cada um dos ~80+ fontes, o
modelo lê o texto (com os links anotados por fetch.py) e devolve os achados
já estruturados.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import anthropic

from .db import Achado

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """\
Você lê o conteúdo textual de páginas de portais institucionais (tribunais, \
corregedorias, associações de cartório, portais legislativos) e extrai uma \
lista dos atos normativos, provimentos, notícias regulatórias ou publicações \
legislativas apresentados nessa página.

Cada link relevante no texto aparece anotado como "[[LINK: <url>]]" logo após \
o texto do link — use essa URL no campo "link" de cada achado.

Extraia apenas itens que sejam de fato atos normativos, provimentos, \
resoluções, notícias sobre mudanças regulatórias, ou publicações legislativas \
relevantes para cartórios extrajudiciais (registro de imóveis, notas, \
protesto, RCPN) e para a área jurídica em geral. Ignore menus, banners, \
propagandas, links de redes sociais e conteúdo sem relação com atos \
normativos/legislativos.

Se a página não tiver nenhum item relevante, devolva uma lista vazia — não \
invente itens.\
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "achados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {
                        "type": "string",
                        "description": "Título do ato/notícia, como aparece na página.",
                    },
                    "data_publicacao": {
                        "type": "string",
                        "description": (
                            "Data de publicação no formato ISO-8601 (AAAA-MM-DD) quando "
                            "identificável; caso contrário, string vazia."
                        ),
                    },
                    "tipo_ato": {
                        "type": "string",
                        "description": (
                            "Tipo do ato quando identificável (ex.: Provimento, Resolução, "
                            "Lei, Decreto, Portaria, Notícia); string vazia se não identificável."
                        ),
                    },
                    "resumo": {
                        "type": "string",
                        "description": "Resumo de 1-2 frases do conteúdo do ato/notícia.",
                    },
                    "link": {
                        "type": "string",
                        "description": "URL absoluta extraída da anotação [[LINK: ...]] correspondente.",
                    },
                },
                "required": ["titulo", "data_publicacao", "tipo_ato", "resumo", "link"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["achados"],
    "additionalProperties": False,
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def extrair_achados(
    *,
    fonte_id: str,
    fonte_nome: str,
    categoria: str,
    estado: Optional[str],
    texto_pagina: str,
    url_pagina: str,
) -> list[Achado]:
    """Chama o Haiku 4.5 para extrair achados estruturados do texto da página."""
    if not texto_pagina.strip():
        return []

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Página de origem: {fonte_nome} ({url_pagina})\n\n"
                    f"Conteúdo:\n{texto_pagina}"
                ),
            }
        ],
    )

    texto_resposta = next(
        (bloco.text for bloco in response.content if bloco.type == "text"), None
    )
    if texto_resposta is None:
        logger.warning("Resposta do modelo sem bloco de texto para fonte %s", fonte_id)
        return []

    try:
        dados = json.loads(texto_resposta)
    except json.JSONDecodeError:
        logger.error("Falha ao decodificar JSON da extração para fonte %s: %r", fonte_id, texto_resposta[:500])
        return []

    achados: list[Achado] = []
    for item in dados.get("achados", []):
        link = (item.get("link") or "").strip()
        titulo = (item.get("titulo") or "").strip()
        if not link or not titulo:
            continue  # sem link ou título, não é um achado utilizável
        achados.append(
            Achado(
                fonte_id=fonte_id,
                fonte_nome=fonte_nome,
                categoria=categoria,
                estado=estado,
                titulo=titulo,
                data_publicacao=(item.get("data_publicacao") or "").strip() or None,
                tipo_ato=(item.get("tipo_ato") or "").strip() or None,
                resumo=(item.get("resumo") or "").strip() or None,
                link=link,
            )
        )
    return achados


_TITULO_MAX = 140


def achados_de_atos_cnj(
    atos: list[dict],
    *,
    fonte_id: str,
    fonte_nome: str,
    categoria: str,
    estado: Optional[str],
) -> list[Achado]:
    """Converte os dicts crus de fetch.buscar_atos_cnj() em Achado, sem
    chamar o modelo — todo item que a API do CNJ devolve já é, por
    definição, um ato normativo publicado (não uma notícia a filtrar), então
    não há decisão de relevância a delegar ao Claude aqui.
    """
    achados: list[Achado] = []
    for ato in atos:
        link = (ato.get("link") or "").strip()
        tipo = (ato.get("tipo") or "").strip()
        numero = ato.get("numero")
        if not link or not tipo:
            continue

        identificacao = f"{tipo} nº {numero}" if numero else tipo
        ementa = (ato.get("ementa") or "").strip()
        if ementa:
            resumo_curto = ementa if len(ementa) <= _TITULO_MAX else ementa[:_TITULO_MAX].rsplit(" ", 1)[0] + "…"
            titulo = f"{identificacao} — {resumo_curto}"
        else:
            titulo = identificacao

        situacao = (ato.get("situacao") or "").strip()
        resumo = ementa or None
        if resumo and situacao:
            resumo = f"{resumo} [Situação: {situacao}]"

        achados.append(
            Achado(
                fonte_id=fonte_id,
                fonte_nome=fonte_nome,
                categoria=categoria,
                estado=estado,
                titulo=titulo,
                data_publicacao=ato.get("data_publicacao"),
                tipo_ato=tipo or None,
                resumo=resumo,
                link=link,
            )
        )
    return achados
