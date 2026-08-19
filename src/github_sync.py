"""Sincroniza o banco local de volta ao GitHub depois de uma triagem manual.

Por que isso existe: o Streamlit Community Cloud roda o painel num container
que clona o repositório na hora do deploy, mas nunca escreve de volta. Antes
deste módulo, `db.atualizar_status()` só gravava no SQLite local dentro
desse container efêmero — a classificação "pertinente"/"não pertinente"
nunca chegava no `data/normativas.db` versionado no GitHub, que é o que o
Pedido 02 lê via checkout read-only. Resultado: a Karina marcava um achado
como pertinente no painel e ele nunca aparecia no Pedido 02.

A correção usa a Contents API do GitHub (não `git push`) porque o container
do Streamlit não tem um remote autenticado configurado, e a Contents API já
resolve concorrência via `sha` (rejeita a escrita se o arquivo mudou desde a
leitura, em vez de sobrescrever silenciosamente).
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

REPO = "Dex057/scraping-normativas-legislativas"
BRANCH = "main"
DB_RELATIVE_PATH = "data/normativas.db"
COMMIT_MESSAGE = "chore: atualiza triagem de achados via painel [skip ci]"


def _token() -> str | None:
    """Busca o token em st.secrets (Streamlit Cloud) ou variável de ambiente
    (uso local/testes). Streamlit não está disponível fora do painel, por
    isso o import é local e tolerante a falha."""
    try:
        import streamlit as st

        if "GITHUB_WRITE_TOKEN" in st.secrets:
            return st.secrets["GITHUB_WRITE_TOKEN"]
    except Exception:
        pass
    return os.environ.get("GITHUB_WRITE_TOKEN")


def commit_db_to_github(db_path: Path) -> tuple[bool, str]:
    """Comita o arquivo local de volta ao GitHub via Contents API.

    Nunca levanta exceção — uma falha de sincronização não pode quebrar a
    interação da Karina no painel. Retorna (sucesso, mensagem) para o
    chamador decidir como exibir o resultado.
    """
    token = _token()
    if not token:
        return False, (
            "GITHUB_WRITE_TOKEN não configurado nos secrets do Streamlit — a "
            "alteração ficou só nesta sessão e será perdida no próximo "
            "redeploy. Configure o secret para persistir (ver "
            "docs/CONFIGURACAO_CREDENCIAIS.md)."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    api_url = f"https://api.github.com/repos/{REPO}/contents/{DB_RELATIVE_PATH}"

    try:
        with httpx.Client(timeout=30) as client:
            atual = client.get(api_url, headers=headers, params={"ref": BRANCH})
            atual.raise_for_status()
            sha_atual = atual.json()["sha"]

            conteudo = base64.b64encode(db_path.read_bytes()).decode("ascii")
            resp = client.put(
                api_url,
                headers=headers,
                json={
                    "message": COMMIT_MESSAGE,
                    "content": conteudo,
                    "sha": sha_atual,
                    "branch": BRANCH,
                },
            )
            resp.raise_for_status()
        return True, "Alteração salva no repositório."
    except httpx.HTTPError as exc:
        logger.error("Falha ao sincronizar banco com o GitHub: %s", exc)
        return False, (
            f"Falha ao salvar no repositório (a alteração ficou só nesta "
            f"sessão): {exc}"
        )
