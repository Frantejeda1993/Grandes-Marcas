"""pages/categoria.py — Vista por Categoría.

Para cada categoría definida (ordenadas por código):
  · Muestra todos los artículos con código de categoría <= al de esa categoría
  · Agrupa los artículos por familia en filas expandibles
  · Muestra las sumas de EMA, Sem-2, Sem-1, Sem actual, Anual, Stock
  · Stock = TODAS las tiendas del filtro
  · Tiendas = "todas_con_mov (solo_cat_o_menor)"
  · Cobertura = "% todas las tiendas (% cat_o_menor)"
  · Sin tabla de categorías superior

Los KPIs de ventas se calculan sobre los datos filtrados del sidebar (todos los stores).
"""
import streamlit as st
import pandas as pd
import numpy as np

from core.kpi import compute_kpis, enrich_with_masters
from core.firestore import load_collection
from components.kpi_cards import empty_state
from pages.tienda import _render_store_kpi_table


# ─── Página principal ─────────────────────────────────────────────────────────

def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>\U0001f5c2\ufe0f Vista por Categor\u00eda</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:20px;'>"
        "Art\u00edculos agrupados por categor\u00eda y familia</p>",
        unsafe_allow_html=True,
    )

    df_f        = st.session_state.get("df_filtered", pd.DataFrame())
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

    # Mapa código → id de categoría
    cat_cod_map = {}
    for c in categorias:
        try:
            cat_cod_map[c["_id"]] = int(c.get("cod_categoria", 999))
        except Exception:
            cat_cod_map[c["_id"]] = 999

    art_cat_id = {a.get("cod_articulo", ""): a.get("categoria_id", "") for a in cat_art}

    # Mapa tienda → código numérico de categoría
    tienda_cat_id  = {a.get("nombre_tienda", ""): a.get("categoria_id", "") for a in cat_tienda}
    tienda_cod_map = {t: cat_cod_map.get(cid, 999) for t, cid in tienda_cat_id.items()}

    # Última semana disponible
    latest_key = int(df_f["sort_key"].max()) if not df_f.empty else 0
    df_latest  = df_f[df_f["sort_key"] == latest_key]

    # ── Calcular KPIs de artículos (sobre TODOS los stores del filtro) ────────
    with st.spinner("Calculando KPIs\u2026"):
        kpis_raw = compute_kpis(df_f, semanas_obj)

    if kpis_raw.empty:
        empty_state()
        return

    kpis = enrich_with_masters(kpis_raw, cat_art, familia_art, categorias, familias)

    # Código numérico de categoría por artículo
    kpis["_art_cod"] = kpis["cod_articulo"].map(
        lambda x: cat_cod_map.get(art_cat_id.get(x, ""), 999)
    )

    # ── Controles ─────────────────────────────────────────────────────────────
    sort_options = {
        "Ventas actuales \u2193": ("sem_actual", False),
        "Stock \u2193":           ("stock_actual", False),
        "EMA \u2193":             ("ema", False),
        "Anual \u2193":           ("ventas_anual", False),
        "Sem. Stock \u2191":      ("semanas_stock", True),
    }
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        sort_sel = st.selectbox(
            "Ordenar art\u00edculos por", list(sort_options.keys()), key="sort_cat"
        )
    with col2:
        expand_cat = st.toggle("Expandir categor\u00edas", value=False, key="expand_cat")
    with col3:
        expand_fam = st.toggle("Expandir familias", value=False, key="expand_fam")

    sort_col, sort_asc = sort_options[sort_sel]

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── Iterar categorías ordenadas por código ────────────────────────────────
    cats_sorted = sorted(categorias, key=lambda c: cat_cod_map.get(c["_id"], 999))

    # Todas las tiendas activas en el filtro
    all_filtered_stores = set(df_f["nombre_tienda"].dropna().unique())

    # Mapa tienda -> cliente para filtrar lógicamente por categoría
    if "nombre_cliente" in df_f.columns:
        tienda_cliente_map = df_f.groupby("nombre_tienda")["nombre_cliente"].first().to_dict()
    else:
        tienda_cliente_map = {}

    for cat in cats_sorted:
        cat_id      = cat["_id"]
        cat_code    = cat_cod_map.get(cat_id, 999)
        cat_nombre  = cat.get("nombre", cat_id)
        cat_cod_str = cat.get("cod_categoria", "")
        cat_client  = cat.get("cliente", "")

        # Etiqueta: "(Cliente) Código - Nombre"
        if cat_client:
            cat_label = f"({cat_client}) {cat_cod_str} - {cat_nombre}"
        else:
            cat_label = f"{cat_cod_str} - {cat_nombre}"

        # Artículos obligatorios para esta categoría (cod_art <= cat_code)
        cat_kpis = kpis[kpis["_art_cod"] <= cat_code].copy()

        if cat_kpis.empty:
            continue

        # Tiendas del cliente de esta categoría
        if cat_client:
            cat_client_stores = {t for t in all_filtered_stores if tienda_cliente_map.get(t) == cat_client}
        else:
            cat_client_stores = all_filtered_stores

        # ── Métricas de tiendas ───────────────────────────────────────────────
        # Tiendas con código >= cat_code (obligatorias para esta categoría)
        cat_obligatory_stores = {
            t for t in cat_client_stores
            if cat_code <= tienda_cod_map.get(t, 999) < 999
        }
        n_cat_stores = len(cat_obligatory_stores)

        # Históricas del cliente (o globales si no hay cliente)
        df_f_client = df_f[df_f["nombre_tienda"].isin(cat_client_stores)]
        df_lat_client = df_latest[df_latest["nombre_tienda"].isin(cat_client_stores)]

        tiendas_all_art_client = df_f_client.groupby("cod_articulo")["nombre_tienda"].nunique()
        tiendas_all_stock_client = df_lat_client[df_lat_client["stock"] > 0].groupby("cod_articulo")["nombre_tienda"].nunique()
        stock_all_client = df_lat_client.groupby("cod_articulo")["stock"].sum()

        if n_cat_stores > 0:
            df_lat_cat = df_latest[df_latest["nombre_tienda"].isin(cat_obligatory_stores)]
            tiendas_cat_stock = df_lat_cat[df_lat_cat["stock"] > 0].groupby("cod_articulo")["nombre_tienda"].nunique()
            stock_cat_amount = df_lat_cat.groupby("cod_articulo")["stock"].sum()
        else:
            tiendas_cat_stock = pd.Series(dtype=float)
            stock_cat_amount = pd.Series(dtype=float)

        all_t = cat_kpis["cod_articulo"].map(tiendas_all_art_client).fillna(0).astype(int)
        cat_kpis["total_tiendas"] = [f"{a} ({n_cat_stores})" for a in all_t]

        # Ud/Tienda: "stock / all_t (stock_cat / n_cat_stores)"
        stock_art_client = cat_kpis["cod_articulo"].map(stock_all_client).fillna(0)
        ud_all = (stock_art_client / all_t.replace(0, 1)).round(1)

        if n_cat_stores > 0:
            stock_art_cat = cat_kpis["cod_articulo"].map(stock_cat_amount).fillna(0)
            ud_cat = (stock_art_cat / n_cat_stores).round(1)
        else:
            ud_cat = pd.Series(0.0, index=cat_kpis.index)

        cat_kpis["ud_por_tienda"] = [f"{a:.1f} ({c:.1f})" for a, c in zip(ud_all.values, ud_cat.values)]

        # Cobertura: "tiendas con stock / all_t (tiendas cat con stock / n_cat_stores)"
        cob_all = (
            cat_kpis["cod_articulo"].map(tiendas_all_stock_client).fillna(0)
            / all_t.replace(0, 1) * 100
        ).round(1)
        if n_cat_stores > 0:
            cob_cat = (
                cat_kpis["cod_articulo"].map(tiendas_cat_stock).fillna(0)
                / n_cat_stores * 100
            ).round(1)
        else:
            cob_cat = pd.Series(0.0, index=cat_kpis.index)

        cat_kpis["cobertura_pct"] = [
            f"{a:.1f}% ({c:.1f}%)"
            for a, c in zip(cob_all.values, cob_cat.values)
        ]

        # Totales de la categoría
        total_ema    = cat_kpis["ema"].sum()
        total_sem_m2 = cat_kpis["sem_m2"].sum()
        total_sem_m1 = cat_kpis["sem_m1"].sum()
        total_sem    = cat_kpis["sem_actual"].sum()
        total_anual  = cat_kpis["ventas_anual"].sum()
        total_stock  = cat_kpis["stock_actual"].sum()
        n_arts       = len(cat_kpis)

        with st.expander(
            f"\U0001f5c2\ufe0f {cat_label}"
            f"  \u00b7  {n_arts} arts"
            f"  \u00b7  EMA: {total_ema:,.1f}"
            f"  \u00b7  Sem-2: {total_sem_m2:,.0f}"
            f"  \u00b7  Sem-1: {total_sem_m1:,.0f}"
            f"  \u00b7  Sem: {total_sem:,.0f}"
            f"  \u00b7  Anual: {total_anual:,.0f}"
            f"  \u00b7  Stock: {total_stock:,.0f}",
            expanded=expand_cat,
        ):
            # ── Agrupar por familia (filas expandibles) ───────────────────────
            familias_con = sorted(
                f for f in cat_kpis["familia"].unique() if f != "Sin familia"
            )
            sin_fam = cat_kpis[cat_kpis["familia"] == "Sin familia"]

            for fam in familias_con:
                fam_kpis = (
                    cat_kpis[cat_kpis["familia"] == fam]
                    .copy()
                    .sort_values(sort_col, ascending=sort_asc, na_position="last")
                )
                if fam_kpis.empty:
                    continue

                fam_ema    = fam_kpis["ema"].sum()
                fam_sem_m2 = fam_kpis["sem_m2"].sum()
                fam_sem_m1 = fam_kpis["sem_m1"].sum()
                fam_sem    = fam_kpis["sem_actual"].sum()
                fam_anual  = fam_kpis["ventas_anual"].sum()
                fam_stock  = fam_kpis["stock_actual"].sum()

                with st.expander(
                    f"\U0001f4e6 {fam}"
                    f"  \u00b7  {len(fam_kpis)} arts"
                    f"  \u00b7  EMA: {fam_ema:,.1f}"
                    f"  \u00b7  Sem-2: {fam_sem_m2:,.0f}"
                    f"  \u00b7  Sem-1: {fam_sem_m1:,.0f}"
                    f"  \u00b7  Sem: {fam_sem:,.0f}"
                    f"  \u00b7  Anual: {fam_anual:,.0f}"
                    f"  \u00b7  Stock: {fam_stock:,.0f}",
                    expanded=expand_fam,
                ):
                    _render_store_kpi_table(fam_kpis)

            # Artículos sin familia asignada
            if not sin_fam.empty:
                sin_fam = sin_fam.sort_values(
                    sort_col, ascending=sort_asc, na_position="last"
                )
                st.markdown(
                    "<div style='margin:8px 0 4px;padding:4px 10px;"
                    "border-left:2px solid #374151;"
                    "font-size:0.78rem;color:#6b7280;'>"
                    "Sin familia asignada</div>",
                    unsafe_allow_html=True,
                )
                _render_store_kpi_table(sin_fam)
