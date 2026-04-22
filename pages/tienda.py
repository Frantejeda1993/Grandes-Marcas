"""pages/tienda.py — Vista detallada por Tienda.

Muestra cada tienda con:
  · Categoría de la tienda
  · Artículos con cualquier movimiento (ventas, devoluciones o stock)
  · Separados en Obligatorios (categoría igual o inferior) y Opcionales (superior)
  · Familias como filas expandibles

La función render_store_article_detail es importada por cliente.py.
"""
import streamlit as st
import pandas as pd
import numpy as np

from core.kpi import compute_article_store_kpis, enrich_with_masters
from core.firestore import load_collection
from components.kpi_cards import empty_state


# ─── Utilidades de formato ────────────────────────────────────────────────────

def _fmt_ss(v):
    """Semanas de stock → texto."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "Sin rot."
    return f"{v:.1f}"


# ─── Tabla KPI compartida ────────────────────────────────────────────────────

def _render_store_kpi_table(kpis: pd.DataFrame):
    """Renderiza tabla KPI para vista de tienda o categoría.

    - Sem -2 y Sem -1: muestra 'ventas (stock del mismo periodo)'
    - total_tiendas / cobertura_pct: admite string (Categoría) o numérico (Tienda)
    """
    if kpis.empty:
        return

    available = [
        "nombre_articulo", "marca", "categoria",
        "ema", "sem_m2", "sem_m1", "sem_actual",
        "ventas_anual", "stock_actual", "semanas_stock",
        "total_tiendas", "ud_por_tienda", "cobertura_pct",
        "alerta",
    ]
    cols = [c for c in available if c in kpis.columns]
    display = kpis[cols].copy()

    # Identificamos qué columnas traen el par (X) (es decir, vienen de la vista Categoría)
    is_cat_view = "total_tiendas" in kpis.columns and kpis["total_tiendas"].dtype == object
    has_m2_stk = "stock_m2" in kpis.columns
    has_m1_stk = "stock_m1" in kpis.columns

    col_sem_m2 = "Sem -2 (Stock)" if has_m2_stk else "Sem -2"
    col_sem_m1 = "Sem -1 (Stock)" if has_m1_stk else "Sem -1"
    col_tiendas = "Tiendas (Cat)" if is_cat_view else "Tiendas"
    col_cob = "Cob. % (Cat)" if is_cat_view else "Cobertura %"

    col_ud = "Ud/Tienda (Cat)" if is_cat_view else "Ud/Tienda"

    rename_map = {
        "nombre_articulo": "Artículo",
        "marca":           "Marca",
        "categoria":       "Categoría",
        "ema":             "EMA",
        "sem_m2":          col_sem_m2,
        "sem_m1":          col_sem_m1,
        "sem_actual":      "Sem actual",
        "ventas_anual":    "Anual",
        "stock_actual":    "Stock",
        "semanas_stock":   "Sem. Stock",
        "total_tiendas":   col_tiendas,
        "ud_por_tienda":   col_ud,
        "cobertura_pct":   col_cob,
        "alerta":          "Estado",
    }
    display = display.rename(
        columns={k: v for k, v in rename_map.items() if k in display.columns}
    )

    if "Sem. Stock" in display.columns:
        display["Sem. Stock"] = display["Sem. Stock"].apply(_fmt_ss)

    # ── Sem -2: ventas + stock entre paréntesis del mismo período ─────────────
    if col_sem_m2 in display.columns and has_m2_stk:
        display[col_sem_m2] = [
            f"{int(v)} ({int(s)})"
            for v, s in zip(
                kpis["sem_m2"].fillna(0).values,
                kpis["stock_m2"].fillna(0).values,
            )
        ]

    # ── Sem -1: ventas + stock entre paréntesis del mismo período ─────────────
    if col_sem_m1 in display.columns and has_m1_stk:
        display[col_sem_m1] = [
            f"{int(v)} ({int(s)})"
            for v, s in zip(
                kpis["sem_m1"].fillna(0).values,
                kpis["stock_m1"].fillna(0).values,
            )
        ]

    # ── Column config ─────────────────────────────────────────────────────────
    config_dict = {
        "Artículo":   st.column_config.TextColumn(width="large"),
        "Marca":        st.column_config.TextColumn(width="small"),
        "Categoría": st.column_config.TextColumn(width="medium"),
        "EMA":          st.column_config.NumberColumn(format="%.1f", width="small"),
        "Sem actual":   st.column_config.NumberColumn(format="%.0f", width="small"),
        "Anual":        st.column_config.NumberColumn(format="%,.0f", width="small"),
        "Stock":        st.column_config.NumberColumn(format="%,.0f", width="small"),
        "Sem. Stock":   st.column_config.TextColumn(width="small"),
        "Estado":       st.column_config.TextColumn(width="small"),
    }
    config_dict[col_sem_m2] = st.column_config.TextColumn(width="medium") if has_m2_stk else st.column_config.NumberColumn(format="%.0f", width="small")
    config_dict[col_sem_m1] = st.column_config.TextColumn(width="medium") if has_m1_stk else st.column_config.NumberColumn(format="%.0f", width="small")

    col_config = {}
    for col, cfg in config_dict.items():
        if col in display.columns:
            col_config[col] = cfg

    # Tiendas: string (Categoría) o numérico (Tienda)
    if col_tiendas in display.columns:
        if display[col_tiendas].dtype == object:
            col_config[col_tiendas] = st.column_config.TextColumn(width="medium")
        else:
            col_config[col_tiendas] = st.column_config.NumberColumn(format="%d", width="small")

    # Ud/Tienda: string o numérico
    if col_ud in display.columns:
        if display[col_ud].dtype == object:
            col_config[col_ud] = st.column_config.TextColumn(width="medium")
        else:
            col_config[col_ud] = st.column_config.NumberColumn(format="%.1f", width="small")


    # Cobertura %: string (Categoría) o barra de progreso (Tienda)
    if col_cob in display.columns:
        if display[col_cob].dtype == object:
            col_config[col_cob] = st.column_config.TextColumn(width="medium")
        else:
            col_config[col_cob] = st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.1f%%", width="medium"
            )

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=38 + len(display) * 36,
        column_config=col_config,
    )


# ─── Detalle de artículos por tienda (compartido con cliente.py) ──────────────

def render_store_article_detail(
    kpis_enriched: pd.DataFrame,
    store_name: str,
    store_cat_cod: int,
    store_client: str = "",
):
    """Renderiza artículos de una tienda específica con separación Obligatorio/Opcional.

    Parámetros:
        kpis_enriched  — DataFrame pre-enriquecido con columnas: nombre_tienda,
                         cod_articulo, nombre_articulo, marca, categoria, familia,
                         _art_cod, ema, sem_m2, sem_m1, sem_actual, ventas_anual,
                         stock_actual, semanas_stock, alerta.
        store_name     — Nombre de la tienda a mostrar.
        store_cat_cod  — Código numérico de categoría de la tienda.
    """
    kpis_store = kpis_enriched[kpis_enriched["nombre_tienda"] == store_name].copy()

    if store_client:
        all_arts = kpis_enriched.drop_duplicates(subset=["cod_articulo"]).copy()
        
        # Filtramos artículos obligatorios del mismo cliente que no están en kpis_store
        obligatory_arts = all_arts[
            (all_arts["art_cliente"] == store_client) &
            (all_arts["_art_cod"] <= store_cat_cod) &
            (all_arts["_art_cod"] != 999)
        ]
        
        missing_arts = obligatory_arts[~obligatory_arts["cod_articulo"].isin(kpis_store["cod_articulo"])].copy()
        
        if not missing_arts.empty:
            for col in ["ema", "sem_m2", "sem_m1", "sem_actual", "ventas_anual", "stock_actual"]:
                if col in missing_arts.columns:
                    missing_arts[col] = 0.0
            
            if "semanas_stock" in missing_arts.columns:
                missing_arts["semanas_stock"] = np.nan
                
            missing_arts["alerta"] = "Artículo obligatorio faltante"
            missing_arts["nombre_tienda"] = store_name
            kpis_store = pd.concat([kpis_store, missing_arts], ignore_index=True)

    if kpis_store.empty:
        st.caption("Sin artículos asignados ni con movimiento registrado en esta tienda.")
        return

    # Clasificar obligatorio / opcional
    kpis_store["_es_obligatorio"] = (
        (kpis_store["_art_cod"] <= store_cat_cod) &
        (kpis_store["_art_cod"] != 999)
    )

    for is_obs in [True, False]:
        tipo_kpis = kpis_store[kpis_store["_es_obligatorio"] == is_obs].copy()
        if tipo_kpis.empty:
            continue

        color = "#4f8ef7" if is_obs else "#9ca3af"
        lbl = "\U0001f4cd Obligatorios \u2014 misma categor\u00eda o inferior" if is_obs else "\u2795 Opcionales \u2014 categor\u00eda superior"
        total_ema    = tipo_kpis["ema"].sum()
        total_sem_m2 = tipo_kpis["sem_m2"].sum()
        total_sem_m1 = tipo_kpis["sem_m1"].sum()
        total_sem    = tipo_kpis["sem_actual"].sum()
        total_anual  = tipo_kpis["ventas_anual"].sum()
        total_stock  = tipo_kpis["stock_actual"].sum()

        st.markdown(
            f"<div style='margin:12px 0 6px;padding:8px 12px;"
            f"background:linear-gradient(90deg,{color}22,transparent);"
            f"border-left:3px solid {color};border-radius:0 6px 6px 0;'>"
            f"<span style='font-size:0.85rem;color:{color};font-weight:700;'>{lbl}</span>"
            f"<span style='color:#6b7280;font-size:0.78rem;margin-left:14px;'>"
            f"EMA: <b style='color:#9ca3af;'>{total_ema:,.1f}</b> &nbsp;·&nbsp; "
            f"Sem-2: <b style='color:#9ca3af;'>{total_sem_m2:,.0f}</b> &nbsp;·&nbsp; "
            f"Sem-1: <b style='color:#9ca3af;'>{total_sem_m1:,.0f}</b> &nbsp;·&nbsp; "
            f"Sem: <b style='color:#9ca3af;'>{total_sem:,.0f}</b> &nbsp;·&nbsp; "
            f"Anual: <b style='color:#9ca3af;'>{total_anual:,.0f}</b> &nbsp;·&nbsp; "
            f"Stock: <b style='color:#9ca3af;'>{total_stock:,.0f}</b>"
            f"</span></div>",
            unsafe_allow_html=True,
        )

        # Agrupar por familia
        familias_con = sorted(f for f in tipo_kpis["familia"].unique() if f != "Sin familia")
        sin_fam = tipo_kpis[tipo_kpis["familia"] == "Sin familia"]

        for fam in familias_con:
            fam_kpis = tipo_kpis[tipo_kpis["familia"] == fam].copy()
            if fam_kpis.empty:
                continue
            fam_ema    = fam_kpis["ema"].sum()
            fam_sem_m2 = fam_kpis["sem_m2"].sum()
            fam_sem_m1 = fam_kpis["sem_m1"].sum()
            fam_sem    = fam_kpis["sem_actual"].sum()
            fam_anual  = fam_kpis["ventas_anual"].sum()
            fam_stock  = fam_kpis["stock_actual"].sum()

            with st.expander(
                f"\U0001f4e6 {fam}  ·  {len(fam_kpis)} arts"
                f"  ·  EMA: {fam_ema:,.1f}"
                f"  ·  Sem-2: {fam_sem_m2:,.0f}"
                f"  ·  Sem-1: {fam_sem_m1:,.0f}"
                f"  ·  Sem: {fam_sem:,.0f}"
                f"  ·  Anual: {fam_anual:,.0f}"
                f"  ·  Stock: {fam_stock:,.0f}",
                expanded=False,
            ):
                _render_store_kpi_table(fam_kpis)

        if not sin_fam.empty:
            st.markdown(
                "<div style='margin:6px 0 2px;padding:4px 8px;"
                "border-left:2px solid #374151;font-size:0.78rem;color:#6b7280;'>"
                "Sin familia asignada</div>",
                unsafe_allow_html=True,
            )
            _render_store_kpi_table(sin_fam)


# ─── Página principal ─────────────────────────────────────────────────────────

def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>\U0001f3ea Vista por Tienda</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:20px;'>"
        "Art\u00edculos por tienda \u00b7 categor\u00eda obligatoria y opcional</p>",
        unsafe_allow_html=True,
    )

    df_f = st.session_state.get("df_filtered", pd.DataFrame())
    semanas_obj = st.session_state.get("semanas_objetivo", 8)

    if df_f is None or df_f.empty:
        empty_state()
        return

    # Cargar maestros
    cat_art     = load_collection("asignaciones_cat_articulo")
    cat_tienda  = load_collection("asignaciones_cat_tienda")
    familia_art = load_collection("asignaciones_familia")
    categorias  = load_collection("categorias")
    familias    = load_collection("familias")

    # Mapas de categoría
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

    tienda_cat_id   = {a.get("nombre_tienda", ""): a.get("categoria_id", "") for a in cat_tienda}
    tienda_cod_map  = {t: cat_cod_map.get(cid, 999) for t, cid in tienda_cat_id.items()}
    tienda_cat_name = {t: cat_name_map.get(cid, "Sin categor\u00eda") for t, cid in tienda_cat_id.items()}
    art_cat_id      = {a.get("cod_articulo", ""): a.get("categoria_id", "") for a in cat_art}

    # Calcular KPIs (tienda, artículo)
    with st.spinner("Calculando KPIs por tienda y art\u00edculo\u2026"):
        all_kpis = compute_article_store_kpis(df_f, semanas_obj)

    if all_kpis.empty:
        empty_state()
        return

    # Enriquecer una sola vez
    all_kpis = enrich_with_masters(all_kpis, cat_art, familia_art, categorias, familias)
    all_kpis["_art_cod"] = all_kpis["cod_articulo"].map(
        lambda x: cat_cod_map.get(art_cat_id.get(x, ""), 999)
    )

    # Controles
    col1, col2 = st.columns([3, 1])
    with col2:
        expand_all = st.toggle("Expandir todo", value=False, key="expand_tienda")

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    # Una fila por tienda
    stores = sorted(df_f["nombre_tienda"].dropna().unique())
    
    if "nombre_cliente" in df_f.columns:
        tienda_cliente_map = df_f.groupby("nombre_tienda")["nombre_cliente"].first().to_dict()
    else:
        tienda_cliente_map = {}

    for store_name in stores:
        store_cat_cod  = tienda_cod_map.get(store_name, 999)
        store_cat_name = tienda_cat_name.get(store_name, "Sin categor\u00eda")

        store_arts = all_kpis[all_kpis["nombre_tienda"] == store_name]
        n_arts      = len(store_arts)
        ema_total   = store_arts["ema"].sum()
        sem_m2      = store_arts["sem_m2"].sum()
        sem_m1      = store_arts["sem_m1"].sum()
        sem_total   = store_arts["sem_actual"].sum()
        anual_total = store_arts["ventas_anual"].sum()
        stock_total = store_arts["stock_actual"].sum()

        with st.expander(
            f"\U0001f3ea {store_name}  ·  [{store_cat_name}]  ·  {n_arts} arts"
            f"  ·  EMA: {ema_total:,.1f}"
            f"  ·  Sem-2: {sem_m2:,.0f}"
            f"  ·  Sem-1: {sem_m1:,.0f}"
            f"  ·  Sem: {sem_total:,.0f}"
            f"  ·  Anual: {anual_total:,.0f}"
            f"  ·  Stock: {stock_total:,.0f}",
            expanded=expand_all,
        ):
            # Badge de categoría
            st.markdown(
                f"<div style='padding:2px 0 10px;color:#9ca3af;font-size:0.82rem;'>"
                f"\U0001f4c2 Categor\u00eda de la tienda: "
                f"<b style='color:#4f8ef7;'>{store_cat_name}</b></div>",
                unsafe_allow_html=True,
            )

            store_client = tienda_cliente_map.get(store_name, "")
            render_store_article_detail(all_kpis, store_name, store_cat_cod, store_client)
