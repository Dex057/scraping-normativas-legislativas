"""Painel de triagem — Pedido 01.

Exibe o digest consolidado de achados e permite à Karina validar/classificar
cada item como Pertinente / Não pertinente (human-in-the-loop), alimentando
o status que servirá de insumo ao Pedido 02.

Deploy: Streamlit Community Cloud, apontando para este repositório. O banco
(data/normativas.db) é lido diretamente do checkout do repo — não há
servidor de banco separado; ele é atualizado pelo workflow do GitHub Actions
a cada ciclo quinzenal e commitado de volta. A triagem manual feita aqui é
sincronizada de volta ao GitHub a cada clique (ver src/github_sync.py) —
sem isso, a classificação ficaria presa no container efêmero do Streamlit e
nunca chegaria no banco versionado que o Pedido 02 lê.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import db, github_sync

st.set_page_config(page_title="Digest de Normativas — Corpo Técnico", page_icon="⚖️", layout="wide")

db.init_db()


def classificar_e_sincronizar(achado_id: int, status: str, classificacao: str | None) -> None:
    """Grava o status localmente e comita de volta ao GitHub — sem o commit,
    a classificação nunca chega no banco que o Pedido 02 lê (ver
    src/github_sync.py)."""
    db.atualizar_status(achado_id, status, classificacao, "karina")
    ok, mensagem = github_sync.commit_db_to_github(db.DB_PATH)
    if ok:
        st.toast("✅ " + mensagem)
    else:
        st.warning(mensagem)


@st.cache_data(ttl=60)
def carregar_achados() -> pd.DataFrame:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT id, fonte_nome, categoria, estado, titulo, data_publicacao,
                      tipo_ato, resumo, link, capturado_em, status, classificacao
               FROM achados
               ORDER BY capturado_em DESC"""
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


@st.cache_data(ttl=60)
def carregar_ultima_execucao() -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM execucoes ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


st.title("⚖️ Digest de Atualizações Normativas e Legislativas")
st.caption("Pedido 01 — monitoramento quinzenal automatizado, com triagem manual antes da publicação.")

ultima = carregar_ultima_execucao()
if ultima:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Última execução", ultima["iniciada_em"][:10] if ultima["iniciada_em"] else "—")
    col2.metric("Fontes OK", ultima["fontes_ok"] or 0)
    col3.metric("Fontes com falha", ultima["fontes_falha"] or 0)
    col4.metric("Achados novos", ultima["achados_novos"] or 0)
else:
    st.info("Nenhuma execução registrada ainda. Rode `python -m src.orchestrator` para popular o banco.")

df = carregar_achados()

if df.empty:
    st.stop()

st.divider()

# ── Filtros ──────────────────────────────────────────────────────────────
col_a, col_b, col_c = st.columns(3)
with col_a:
    filtro_status = st.multiselect(
        "Status", options=["pendente", "pertinente", "nao_pertinente"], default=["pendente"]
    )
with col_b:
    filtro_categoria = st.multiselect(
        "Categoria", options=sorted(df["categoria"].dropna().unique().tolist())
    )
with col_c:
    filtro_estado = st.multiselect(
        "Estado (UF)", options=sorted(df["estado"].dropna().unique().tolist())
    )

filtrado = df.copy()
if filtro_status:
    filtrado = filtrado[filtrado["status"].isin(filtro_status)]
if filtro_categoria:
    filtrado = filtrado[filtrado["categoria"].isin(filtro_categoria)]
if filtro_estado:
    filtrado = filtrado[filtrado["estado"].isin(filtro_estado)]

st.caption(f"{len(filtrado)} achado(s) exibido(s) de {len(df)} no total.")

# ── Triagem item a item ──────────────────────────────────────────────────
for _, achado in filtrado.iterrows():
    with st.container(border=True):
        cabecalho = f"**{achado['titulo']}**"
        st.markdown(cabecalho)
        # Campos opcionais (estado, tipo_ato, data_publicacao) costumam vir NULL
        # do SQLite. O pandas 3.x representa isso como NaN mesmo em colunas de
        # dtype "str" — NaN é "truthy" (bool(nan) é True) e não é str, então
        # `filter(None, [...])` não filtra e `" · ".join(...)` quebra. Usa
        # pd.notna() explicitamente em vez de confiar em truthiness.
        meta = " · ".join(
            str(valor)
            for valor in [
                achado["fonte_nome"],
                achado["estado"],
                achado["tipo_ato"],
                achado["data_publicacao"],
            ]
            if pd.notna(valor) and str(valor).strip()
        )
        st.caption(meta)
        if pd.notna(achado["resumo"]) and str(achado["resumo"]).strip():
            st.write(achado["resumo"])
        st.markdown(f"[Ver fonte original]({achado['link']})")

        classificacao_atual = achado["classificacao"] if pd.notna(achado["classificacao"]) else None

        col_x, col_y, col_z, col_status = st.columns([1, 1, 2, 1])
        with col_x:
            if st.button("✅ Pertinente", key=f"pert_{achado['id']}"):
                classificar_e_sincronizar(int(achado["id"]), "pertinente", classificacao_atual)
                st.cache_data.clear()
                st.rerun()
        with col_y:
            if st.button("❌ Não pertinente", key=f"npert_{achado['id']}"):
                classificar_e_sincronizar(int(achado["id"]), "nao_pertinente", classificacao_atual)
                st.cache_data.clear()
                st.rerun()
        with col_status:
            st.caption(f"Status: `{achado['status']}`")
