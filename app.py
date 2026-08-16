"""Painel de triagem — Pedido 01.

Exibe o digest consolidado de achados e permite à Karina validar/classificar
cada item como Pertinente / Não pertinente (human-in-the-loop), alimentando
o status que servirá de insumo ao Pedido 02.

Deploy: Streamlit Community Cloud, apontando para este repositório. O banco
(data/normativas.db) é lido diretamente do checkout do repo — não há
servidor de banco separado; ele é atualizado pelo workflow do GitHub Actions
a cada ciclo quinzenal e commitado de volta.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import db

st.set_page_config(page_title="Digest de Normativas — Corpo Técnico", page_icon="⚖️", layout="wide")

db.init_db()


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
        meta = " · ".join(
            filter(
                None,
                [
                    achado["fonte_nome"],
                    achado["estado"],
                    achado["tipo_ato"],
                    achado["data_publicacao"],
                ],
            )
        )
        st.caption(meta)
        if achado["resumo"]:
            st.write(achado["resumo"])
        st.markdown(f"[Ver fonte original]({achado['link']})")

        col_x, col_y, col_z, col_status = st.columns([1, 1, 2, 1])
        with col_x:
            if st.button("✅ Pertinente", key=f"pert_{achado['id']}"):
                db.atualizar_status(int(achado["id"]), "pertinente", achado["classificacao"], "karina")
                st.cache_data.clear()
                st.rerun()
        with col_y:
            if st.button("❌ Não pertinente", key=f"npert_{achado['id']}"):
                db.atualizar_status(int(achado["id"]), "nao_pertinente", achado["classificacao"], "karina")
                st.cache_data.clear()
                st.rerun()
        with col_status:
            st.caption(f"Status: `{achado['status']}`")
