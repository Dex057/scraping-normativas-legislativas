"""Orquestrador do ciclo de varredura quinzenal.

Fluxo (RF01-RF07 do levantamento de requisitos):
  1. Carrega as fontes ativas de config/sources.yaml
  2. Para cada fonte: busca a página, extrai achados via Claude Haiku 4.5
  3. Deduplica contra o histórico (por hash) e persiste só os itens novos
  4. Registra falhas por fonte sem interromper as demais (RNF02)
  5. Ao final, grava um resumo da execução

Uso:
    python -m src.orchestrator
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import yaml

from . import db
from .extract import achados_de_atos_cnj, extrair_achados
from .fetch import buscar_atos_cnj, buscar_pagina

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("orchestrator")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"


def carregar_fontes() -> list[dict]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    fontes = config.get("fontes", [])
    ativas = [f for f in fontes if f.get("ativo") and f.get("url")]
    logger.info("%d fontes ativas de %d configuradas", len(ativas), len(fontes))
    return ativas


def _processar_fonte_cnj_atos(fonte: dict, execucao_id: int) -> tuple[bool, int]:
    """Caminho dedicado para fontes com formato: cnj_atos — a API interna
    do CNJ já devolve atos oficiais estruturados, então pula extract.py/Claude
    inteiramente (ver achados_de_atos_cnj)."""
    fonte_id = fonte["id"]
    try:
        atos = buscar_atos_cnj(fonte["endpoint"])
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao buscar API do CNJ para fonte '%s': %s", fonte_id, exc)
        db.registrar_falha(execucao_id, fonte_id, str(exc))
        return False, 0

    achados = achados_de_atos_cnj(
        atos,
        fonte_id=fonte_id,
        fonte_nome=fonte["nome"],
        categoria=fonte["categoria"],
        estado=fonte.get("estado"),
    )

    novos = 0
    for achado in achados:
        if db.salvar_achado(achado, execucao_id):
            novos += 1

    logger.info(
        "Fonte '%s' (api cnj_atos): %d atos na janela, %d novos (dedup aplicado)",
        fonte_id, len(achados), novos,
    )
    return True, novos


def processar_fonte(fonte: dict, execucao_id: int) -> tuple[bool, int]:
    """Processa uma fonte. Retorna (sucesso, quantidade_de_achados_novos)."""
    fonte_id = fonte["id"]
    modo = fonte.get("modo", "estatico")

    if modo == "api_json" and not fonte.get("endpoint"):
        db.registrar_falha(execucao_id, fonte_id, "modo=api_json sem 'endpoint' configurado em sources.yaml")
        return False, 0

    if modo == "api_json" and fonte.get("formato") == "cnj_atos":
        return _processar_fonte_cnj_atos(fonte, execucao_id)

    # Para modo=api_json (formato wp), a URL a buscar é o endpoint da API,
    # não a página institucional cadastrada em "url" (mantida só como
    # referência humana em sources.yaml).
    url_busca = fonte.get("endpoint") if modo == "api_json" else fonte["url"]

    try:
        conteudo = buscar_pagina(url_busca, modo=modo)
    except Exception as exc:  # noqa: BLE001 — falha de uma fonte não pode derrubar o ciclo
        logger.error("Falha ao buscar fonte '%s': %s", fonte_id, exc)
        db.registrar_falha(execucao_id, fonte_id, str(exc))
        return False, 0

    if conteudo is None:
        db.registrar_falha(execucao_id, fonte_id, "Busca retornou vazio sem levantar exceção")
        return False, 0

    try:
        achados = extrair_achados(
            fonte_id=fonte_id,
            fonte_nome=fonte["nome"],
            categoria=fonte["categoria"],
            estado=fonte.get("estado"),
            texto_pagina=conteudo.texto,
            url_pagina=conteudo.url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha na extração para fonte '%s': %s", fonte_id, exc)
        db.registrar_falha(execucao_id, fonte_id, f"Extração: {exc}")
        return False, 0

    novos = 0
    for achado in achados:
        if db.salvar_achado(achado, execucao_id):
            novos += 1

    logger.info(
        "Fonte '%s': %d achados extraídos, %d novos (dedup aplicado)",
        fonte_id, len(achados), novos,
    )
    return True, novos


def executar_ciclo() -> None:
    db.init_db()
    fontes = carregar_fontes()
    if not fontes:
        logger.warning("Nenhuma fonte ativa configurada — nada a fazer.")
        return

    execucao_id = db.iniciar_execucao()
    logger.info("Execução #%d iniciada", execucao_id)

    fontes_ok = 0
    fontes_falha = 0
    achados_novos_total = 0

    for fonte in fontes:
        sucesso, novos = processar_fonte(fonte, execucao_id)
        if sucesso:
            fontes_ok += 1
        else:
            fontes_falha += 1
        achados_novos_total += novos

    db.finalizar_execucao(execucao_id, fontes_ok, fontes_falha, achados_novos_total)
    logger.info(
        "Execução #%d finalizada: %d fontes OK, %d falharam, %d achados novos",
        execucao_id, fontes_ok, fontes_falha, achados_novos_total,
    )


if __name__ == "__main__":
    try:
        executar_ciclo()
    except Exception:
        logger.exception("Execução do ciclo falhou de forma não tratada")
        sys.exit(1)
