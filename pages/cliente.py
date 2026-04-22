"""pages/cliente.py — Vista jerárquica: Cliente → Categoría → Tienda → Artículos.

Nivel 1: Cliente — suma de KPIs de todas sus tiendas
Nivel 2: Categorías del cliente — suma de KPIs de las tiendas de esa categoría
Nivel 3: Tiendas — KPIs de la tienda (EMA, Sem-2, Sem-1, Sem Actual, Anual, Stock)
Nivel 4: Artículos de la tienda — vista de Tienda (Obligatorios / Opcionales)
"""
import streamlit as st
import pandas as pd
import numpy as np

from core.kpi import compute_store_kpis, compute_article_store_kpis, enrich_with_masters
from core.firestore import load_collection
from components.kpi_cards import empty_state
from pages.tienda import render_store_article_detail


# ─── Helpers de presentación ──────────────────────────────────────────────────

def _agg(df_sub: pd.DataFrame) -> dict:
    """Agrega KPIs de un sub-DataFrame de tiendas."""
    return {
        "ema":          df_sub["ema"].sum(),
        "sem_m2":       df_sub["sem_m2"].sum(),
        "sem_m1":       df_sub["sem_m1"].sum(),
        "sem_actual":   df_sub["sem_actual"].sum(),
        "ventas_anual": df_sub["ventas_anual"].sum(),
        "stock_actual": df_sub["stock_actual"].sum(),
    }


def _label(d: dict, prefix: str = "") -> str:
    """Etiqueta de texto con KPIs para título de expander."""
    return (
        f"{prefix}"
        f"EMA: {d['ema']:,.1f}  "
        f"Sem-2: {d['sem_m2']:,.0f}  "
        f"Sem-1: {d['sem_m1']:,.0f}  "
        f"Sem: {d['sem_actual']:,.0f}  "
        f"Anual: {d['ventas_anual']:,.0f}  "
        f"Stock: {d['stock_actual']:,.0f}"
    )


def _kpi_banner(d: dict):
    """Banner HTML con KPIs detallados (dentro de un expander)."""
    st.markdown(
        f"<div style='background:#111827;border-radius:8px;padding:10px 18px;"
        f"margin:4px 0 14px;border:1px solid #1f2937;"
        f"display:flex;gap:18px;flex-wrap:wrap;align-items:center;'>"
        f"<span style='color:#9ca3af;font-size:0.8rem;'>"
        f"EMA: <b style='color:#e8eaed;'>{d['ema']:,.1f}</b></span>"
        f"<span style='color:#9ca3af;font-size:0.8rem;'>"
        f"Sem -2: <b style='color:#e8eaed;'>{d['sem_m2']:,.0f}</b></span>"
        f"<span style='color:#9ca3af;font-size:0.8rem;'>"
        f"Sem -1: <b style='color:#e8eaed;'>{d['sem_m1']:,.0f}</b></span>"
        f"<span style='color:#9ca3af;font-size:0.8rem;'>"
        f"Sem actual: <b style='color:#4f8ef7;'>{d['sem_actual']:,.0f}</b></span>"
        f"<span style='color:#9ca3af;font-size:0.8rem;'>"
        f"Anual: <b style='color:#e8eaed;'>{d['ventas_anual']:,.0f}</b></span>"
        f"<span style='color:#9ca3af;font-size:0.8rem;'>"
        f"Stock: <b style='color:#e8eaed;'>{d['stock_actual']:,.0f}</b></span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _cat_header(cat_name: str, n_stores: int, d: dict):
    """Cabecera de categoría (nivel 2) dentro del expander de cliente."""
    st.markdown(
        f"<div style='margin:14px 0 6px;padding:8px 14px;"
        f"background:linear-gradient(90deg,#1e3a5f33,transparent);"
        f"border-left:3px solid #2563eb;border-radius:0 6px 6px 0;'>"
        f"<span style='font-size:0.9rem;color:#60a5fa;font-weight:700;'>"
        f"🗂️ {cat_name}</span>"
        f"<span style='color:#6b7280;font-size:0.78rem;margin-left:14px;'>"
        f"{n_stores} tienda{'s' if n_stores != 1 else ''} &nbsp;·&nbsp; "
        f"EMA: <b style='color:#9ca3af;'>{d['ema']:,.1f}</b> &nbsp;·&nbsp; "
        f"Sem-2: <b style='color:#9ca3af;'>{d['sem_m2']:,.0f}</b> &nbsp;·&nbsp; "
        f"Sem-1: <b style='color:#9ca3af;'>{d['sem_m1']:,.0f}</b> &nbsp;·&nbsp; "
        f"Sem: <b style='color:#9ca3af;'>{d['sem_actual']:,.0f}</b> &nbsp;·&nbsp; "
        f"Anual: <b style='color:#9ca3af;'>{d['ventas_anual']:,.0f}</b> &nbsp;·&nbsp; "
        f"Stock: <b style='color:#9ca3af;'>{d['stock_actual']:,.0f}</b>"
        f"</span></div>",
        unsafe_allow_html=True,
    )


# ─── Página principal ─────────────────────────────────────────────────────────

def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>👤 Vista por Cliente</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:20px;'>"
        "Cliente → Categoría → Tienda → Artículos</p>",
        unsafe_allow_html=True,
    )

    df_f       = st.session_state.get("df_filtered", pd.DataFrame())
    semanas_obj = st.session_state.get("semanas_objetivo", 8)

    if df_f is None or df_f.empty:
        empty_state()
        return

    # ── Cargar maestros ───────────────────────────────────────────────────────
    cat_art     = load_collection("asignaciones_cat_articulo")
    cat_tienda  = load_collection("asignaciones_cat_tienda")
    familia_art = load_collection("asignaciones_familia")
    categorias  = load_collection("categorias")
    familias    = load_collection("familias")

    cat_cod_map  = {}
    cat_name_map = {}
    for c in categorias:
        try:
            cat_cod_map[c["_id"]] = int(c.get("cod_categoria", 999))
        except Exception:
            cat_cod_map[c["_id"]] = 999
        cat_name_map[c["_id"]] = (
            f"{c.get('cod_categoria', '')} - {c.get('nombre', c['_id'])}"
        )

    tienda_cat_id  = {a.get("nombre_tienda", ""): a.get("categoria_id", "") for a in cat_tienda}
    tienda_cod_map  = {t: cat_cod_map.get(cid, 999) for t, cid in tienda_cat_id.items()}
    tienda_cat_name = {t: cat_name_map.get(cid, "Sin categoría") for t, cid in tienda_cat_id.items()}
    art_cat_id = {a.get("cod_articulo", ""): a.get("categoria_id", "") for a in cat_art}

    # ── Calcular KPIs por tienda (nivel 1 y 2) ───────────────────────────────
    with st.spinner("Calculando KPIs por tienda…"):
        store_kpis = compute_store_kpis(df_f)

    if store_kpis.empty:
        empty_state()
        return

    # ── Calcular KPIs por (tienda, artículo) (nivel 3 — detalle) ─────────────
    with st.spinner("Calculando KPIs por artículo y tienda…"):
        art_store_kpis = compute_article_store_kpis(df_f, semanas_obj)

    if not art_store_kpis.empty:
        art_store_kpis = enrich_with_masters(
            art_store_kpis, cat_art, familia_art, categorias, familias
        )
        art_store_kpis["_art_cod"] = art_store_kpis["cod_articulo"].map(
            lambda x: cat_cod_map.get(art_cat_id.get(x, ""), 999)
        )

    # Añadir categoría a store_kpis para poder agrupar
    store_kpis["_cat_name"] = store_kpis["nombre_tienda"].map(tienda_cat_name).fillna("Sin categoría")
    store_kpis["_cat_cod"]  = store_kpis["nombre_tienda"].map(tienda_cod_map).fillna(999)

    # ── Controles ─────────────────────────────────────────────────────────────
    _, col2 = st.columns([3, 1])
    with col2:
        expand_all = st.toggle("Expandir todo", value=False, key="expand_cliente")

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── Nivel 1: Clientes ─────────────────────────────────────────────────────
    clients = sorted(store_kpis["nombre_cliente"].dropna().unique())

    for cliente in clients:
        client_stores = store_kpis[store_kpis["nombre_cliente"] == cliente]
        client_agg    = _agg(client_stores)
        n_stores      = len(client_stores)

        with st.expander(
            f"👤 {cliente}  ·  {n_stores} tiendas  ·  {_label(client_agg)}",
            expanded=expand_all,
        ):
            _kpi_banner(client_agg)

            # ── Nivel 2: Categorías dentro del cliente ────────────────────────
            cats = sorted(client_stores["_cat_name"].unique())

            for cat_name in cats:
                cat_stores = client_stores[client_stores["_cat_name"] == cat_name]
                cat_agg    = _agg(cat_stores)
                _cat_header(cat_name, len(cat_stores), cat_agg)

                # ── Nivel 3: Tiendas dentro de la categoría ───────────────────
                for _, store_row in cat_stores.iterrows():
                    store_name    = store_row["nombre_tienda"]
                    store_agg     = store_row.to_dict()
                    store_cat_cod = int(store_row.get("_cat_cod", 999))

                    with st.expander(
                        f"🏪 {store_name}  ·  {_label(store_agg)}",
                        expanded=False,
                    ):
                        # Badge de categoría
                        st.markdown(
                            f"<div style='padding:2px 0 8px;"
                            f"color:#9ca3af;font-size:0.82rem;'>"
                            f"📂 Categoría: "
                            f"<b style='color:#4f8ef7;'>{cat_name}</b></div>",
                            unsafe_allow_html=True,
                        )

                        # ── Nivel 4: Artículos de la tienda ──────────────────
                        if art_store_kpis.empty:
                            st.caption("Sin datos de artículos.")
                        else:
                            render_store_article_detail(
                                art_store_kpis,
                                store_name,
                                store_cat_cod,
                                cliente,
                            )

                st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
