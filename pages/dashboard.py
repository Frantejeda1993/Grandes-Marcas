"""pages/dashboard.py — Dashboard principal con KPIs, tops y alarmas."""
import streamlit as st
import pandas as pd

from core.kpi import (
    compute_kpis, top_tiendas, top_familias, top_categorias, alarmas
)
from core.firestore import load_collection
from components.kpi_cards import kpi_card, section_header, empty_state
from components.charts import bar_horizontal


def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>📊 Dashboard</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:24px;'>"
        "Vista general · últimas 16 semanas</p>",
        unsafe_allow_html=True,
    )

    df = st.session_state.get("df_master", pd.DataFrame())
    df_f = st.session_state.get("df_filtered", pd.DataFrame())
    semanas_obj = st.session_state.get("semanas_objetivo", 8)

    if df_f is None or df_f.empty:
        empty_state("No hay datos cargados. Ve a <b>Inputs</b> para cargar un archivo EDI.")
        return

    # ── KPIs globales ────────────────────────────────────────────────────────
    with st.spinner("Calculando KPIs…"):
        kpis = compute_kpis(df_f, semanas_obj)

    if kpis.empty:
        empty_state()
        return

    total_ventas = df_f.groupby("sort_key").apply(
        lambda g: g["ventas_netas"].sum()
    ).tail(1).sum() if not df_f.empty else 0

    ventas_sem = float(df_f[df_f["sort_key"] == df_f["sort_key"].max()]["ventas_netas"].sum())
    valor_total = float(kpis["valor_anual"].sum())
    n_tiendas = int(df_f["nombre_tienda"].nunique())
    cob_media = float(kpis["cobertura_pct"].mean()) if not kpis.empty else 0.0
    n_art_falta = int((kpis["alerta"] == "Falta").sum())
    n_art_sobre = int((kpis["alerta"] == "Sobrestock").sum())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card("Ventas netas (sem. actual)", f"{ventas_sem:,.0f}", "🛒",
                 color="#4f8ef7", suffix=" ud")
    with col2:
        kpi_card("Valor anual (52 sem.)", f"{valor_total:,.0f}", "💰",
                 color="#00c48c", suffix=" €")
    with col3:
        kpi_card("Tiendas activas", f"{n_tiendas:,}", "🏪", color="#ffb300")
    with col4:
        kpi_card("Cobertura media", f"{cob_media:.1f}", "📦",
                 color="#9c27b0", suffix="%")

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    # Alertas rápidas inline
    ca, cb = st.columns(2)
    with ca:
        st.markdown(
            f"<div style='background:#ff525220;border:1px solid #ff525244;"
            f"border-radius:10px;padding:10px 16px;font-size:0.85rem;color:#ff5252;"
            f"font-weight:600;'>🔴 {n_art_falta} artículo(s) con <b>falta de stock</b></div>",
            unsafe_allow_html=True,
        )
    with cb:
        st.markdown(
            f"<div style='background:#9c27b020;border:1px solid #9c27b044;"
            f"border-radius:10px;padding:10px 16px;font-size:0.85rem;color:#ce93d8;"
            f"font-weight:600;'>🟣 {n_art_sobre} artículo(s) en <b>sobrestock</b></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top:4px;'></div>", unsafe_allow_html=True)

    # ── Tops ─────────────────────────────────────────────────────────────────
    section_header("Top 15 Tiendas", "🏪")
    tu, tv = top_tiendas(df_f, 15)
    col_a, col_b = st.columns(2)
    with col_a:
        if not tu.empty:
            st.plotly_chart(
                bar_horizontal(tu, "unidades", "nombre_tienda",
                               title="Por Unidades vendidas", color="#4f8ef7"),
                width="stretch",
            )
    with col_b:
        if not tv.empty:
            st.plotly_chart(
                bar_horizontal(tv, "valor_total", "nombre_tienda",
                               title="Por Valor (€)", color="#00c48c"),
                width="stretch",
            )

    section_header("Top 15 Familias de Artículos", "🗂️")
    familias_art = load_collection("asignaciones_familia")
    familias = load_collection("familias")
    fu, fv = top_familias(df_f, familias_art, familias, 15)
    col_c, col_d = st.columns(2)
    with col_c:
        if not fu.empty:
            st.plotly_chart(
                bar_horizontal(fu, "unidades", "familia",
                               title="Por Unidades vendidas", color="#ffb300"),
                width="stretch",
            )
    with col_d:
        if not fv.empty:
            st.plotly_chart(
                bar_horizontal(fv, "valor_total", "familia",
                               title="Por Valor (€)", color="#9c27b0"),
                width="stretch",
            )

    section_header("Top 15 Categorías de Tienda", "📋")
    cat_tienda = load_collection("asignaciones_cat_tienda")
    categorias = load_collection("categorias")
    cu, cv = top_categorias(df_f, cat_tienda, categorias, 15)
    col_e, col_f = st.columns(2)
    with col_e:
        if not cu.empty:
            st.plotly_chart(
                bar_horizontal(cu, "unidades", "categoria",
                               title="Por Unidades vendidas", color="#06b6d4"),
                width="stretch",
            )
    with col_f:
        if not cv.empty:
            st.plotly_chart(
                bar_horizontal(cv, "valor_total", "categoria",
                               title="Por Valor (€)", color="#f97316"),
                width="stretch",
            )

    # ── Alarmas ──────────────────────────────────────────────────────────────
    section_header("Alarmas", "🚨")
    alarm_data = alarmas(kpis, df_f)

    tab1, tab2, tab3 = st.tabs([
        "🏪 Tiendas con bajo stock",
        "📦 Artículos – Falta de stock",
        "💤 Sin movimiento",
    ])

    with tab1:
        df_low = alarm_data.get("low_stock_tiendas", pd.DataFrame())
        if not df_low.empty:
            _render_alarm_table(df_low, "Semanas Stock", ascending=True)
        else:
            st.info("No hay tiendas con bajo stock.")

    with tab2:
        df_bajo = alarm_data.get("bajo_stock_art", pd.DataFrame())
        if not df_bajo.empty:
            _render_alarm_table(df_bajo.drop(columns=["alerta_color"], errors="ignore"),
                                "Sem. Stock", ascending=True)
        else:
            st.info("No hay artículos con alerta de Falta.")

    with tab3:
        df_nomov = alarm_data.get("no_movimiento", pd.DataFrame())
        if not df_nomov.empty:
            _render_alarm_table(df_nomov, "Sem. sin venta", ascending=False)
        else:
            st.info("No hay artículos sin movimiento.")


def _render_alarm_table(df: pd.DataFrame, sort_col: str, ascending: bool = True):
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=ascending)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        height=min(400, 38 + len(df) * 35),
    )
