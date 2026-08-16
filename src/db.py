"""Camada de persistência (SQLite) — achados, execuções e status de validação.

O banco é um arquivo versionado no repositório (data/normativas.db). O workflow
do GitHub Actions faz commit dele de volta após cada execução, e o Streamlit
Community Cloud lê o mesmo repositório — por isso não há servidor de banco
separado.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "normativas.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iniciada_em TEXT NOT NULL,
    finalizada_em TEXT,
    fontes_ok INTEGER DEFAULT 0,
    fontes_falha INTEGER DEFAULT 0,
    achados_novos INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS achados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,       -- hash(fonte_id + titulo + link) — chave de dedup
    fonte_id TEXT NOT NULL,
    fonte_nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    estado TEXT,
    titulo TEXT NOT NULL,
    data_publicacao TEXT,            -- ISO-8601 quando disponível; senão texto bruto
    tipo_ato TEXT,
    resumo TEXT,
    link TEXT NOT NULL,
    capturado_em TEXT NOT NULL,      -- timestamp da execução que encontrou o item
    execucao_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',  -- pendente | pertinente | nao_pertinente
    classificacao TEXT,              -- categoria livre definida na triagem (ex.: "extrajudicial", "urgente")
    revisado_por TEXT,
    revisado_em TEXT,
    FOREIGN KEY (execucao_id) REFERENCES execucoes(id)
);

CREATE TABLE IF NOT EXISTS falhas_coleta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execucao_id INTEGER NOT NULL,
    fonte_id TEXT NOT NULL,
    erro TEXT NOT NULL,
    ocorrido_em TEXT NOT NULL,
    FOREIGN KEY (execucao_id) REFERENCES execucoes(id)
);
"""


@dataclass
class Achado:
    fonte_id: str
    fonte_nome: str
    categoria: str
    titulo: str
    link: str
    estado: Optional[str] = None
    data_publicacao: Optional[str] = None
    tipo_ato: Optional[str] = None
    resumo: Optional[str] = None

    @property
    def hash(self) -> str:
        raw = f"{self.fonte_id}|{self.titulo.strip().lower()}|{self.link.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def iniciar_execucao() -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO execucoes (iniciada_em) VALUES (?)", (_now(),)
        )
        return cur.lastrowid


def finalizar_execucao(execucao_id: int, fontes_ok: int, fontes_falha: int, achados_novos: int) -> None:
    with connect() as conn:
        conn.execute(
            """UPDATE execucoes
               SET finalizada_em = ?, fontes_ok = ?, fontes_falha = ?, achados_novos = ?
               WHERE id = ?""",
            (_now(), fontes_ok, fontes_falha, achados_novos, execucao_id),
        )


def registrar_falha(execucao_id: int, fonte_id: str, erro: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO falhas_coleta (execucao_id, fonte_id, erro, ocorrido_em) VALUES (?, ?, ?, ?)",
            (execucao_id, fonte_id, str(erro)[:2000], _now()),
        )


def salvar_achado(achado: Achado, execucao_id: int) -> bool:
    """Insere o achado se ainda não existir (dedup por hash). Retorna True se foi novo."""
    with connect() as conn:
        try:
            conn.execute(
                """INSERT INTO achados
                   (hash, fonte_id, fonte_nome, categoria, estado, titulo, data_publicacao,
                    tipo_ato, resumo, link, capturado_em, execucao_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    achado.hash,
                    achado.fonte_id,
                    achado.fonte_nome,
                    achado.categoria,
                    achado.estado,
                    achado.titulo,
                    achado.data_publicacao,
                    achado.tipo_ato,
                    achado.resumo,
                    achado.link,
                    _now(),
                    execucao_id,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False  # já existe — não é novidade


def atualizar_status(achado_id: int, status: str, classificacao: Optional[str], revisado_por: str) -> None:
    with connect() as conn:
        conn.execute(
            """UPDATE achados
               SET status = ?, classificacao = ?, revisado_por = ?, revisado_em = ?
               WHERE id = ?""",
            (status, classificacao, revisado_por, _now(), achado_id),
        )
