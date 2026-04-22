"""core/kpi.py — Motor de KPIs: EMA, semanas de stock, alertas, cobertura.

Todas las funciones operan sobre DataFrames Pandas en memoria.
Firestore solo se toca al cargar; los filtros y cálculos son puramente locales.
"""
import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, List, Optional, Tuple

# ─── Constantes ───────────────────────────────────────────────────────────────
ALPHA = 0.3
N_WEEKS_EMA = 16
N_WEEKS_YEAR = 52


# ─── Utilidades de semanas ────────────────────────────────────────────────────

def get_sorted_weeks(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve (año, semana, sort_key) únicos, ordenados ascendente."""
    if df.empty:
        return pd.DataFrame(columns=["año", "semana", "sort_key"])
    w = df[["año", "semana"]].drop_duplicates().copy()
    w["sort_key"] = w["año"] * 100 + w["semana"]
    return w.sort_values("sort_key").reset_index(drop=True)


def compute_ema(values: np.ndarray, alpha: float = ALPHA) -> float:
    """EMA con alpha dado. values ordenado del más antiguo al más reciente."""
    if len(values) == 0:
        return 0.0
    ema = float(values[0])
    for v in values[1:]:
        ema = alpha * float(v) + (1.0 - alpha) * ema
    return ema


# ─── Filtros globales ─────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """Aplica los filtros globales al DataFrame maestro."""
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    if filters.get("clientes"):
        mask &= df["nombre_cliente"].isin(filters["clientes"])
    if filters.get("marcas"):
        mask &= df["marca"].isin(filters["marcas"])
    if filters.get("tiendas"):
        mask &= df["nombre_tienda"].isin(filters["tiendas"])
    if filters.get("articulos"):
        mask &= df["nombre_articulo"].isin(filters["articulos"])
    return df[mask].copy()


def get_filter_options(df: pd.DataFrame) -> Dict[str, List]:
    """Extrae listas únicas para cada dimensión de filtro."""
    if df.empty:
        return {"clientes": [], "marcas": [], "tiendas": [], "articulos": []}
    return {
        "clientes": sorted(df["nombre_cliente"].dropna().unique().tolist()),
        "marcas": sorted(df["marca"].dropna().unique().tolist()),
        "tiendas": sorted(df["nombre_tienda"].dropna().unique().tolist()),
        "articulos": sorted(df["nombre_articulo"].dropna().unique().tolist()),
    }


# ─── Cálculo de KPIs por artículo ─────────────────────────────────────────────

def compute_kpis(df: pd.DataFrame, semanas_objetivo: int = 8) -> pd.DataFrame:
    """Calcula KPIs a nivel de artículo sobre el DataFrame filtrado.

    Columnas resultado:
        cod_articulo, nombre_articulo, marca,
        ema, sem_actual, sem_m1, sem_m2, ventas_anual, valor_anual,
        stock_actual, semanas_stock, alerta, alerta_color,
        cobertura_pct, ud_por_tienda, total_tiendas
    """
    if df.empty:
        return pd.DataFrame()

    all_weeks = get_sorted_weeks(df)
    if all_weeks.empty:
        return pd.DataFrame()

    # ── Ventanas temporales ──────────────────────────────────────────────────
    ema_weeks = all_weeks.tail(N_WEEKS_EMA)
    ema_keys = set(ema_weeks["sort_key"])

    year_weeks = all_weeks.tail(N_WEEKS_YEAR)
    year_keys = set(year_weeks["sort_key"])

    latest = all_weeks.iloc[-1]
    wm1 = all_weeks.iloc[-2] if len(all_weeks) >= 2 else None
    wm2 = all_weeks.iloc[-3] if len(all_weeks) >= 3 else None

    latest_key = int(latest["sort_key"])
    latest_año = int(latest["año"])
    latest_sem = int(latest["semana"])

    # ── Subsets ─────────────────────────────────────────────────────────────
    df_ema = df[df["sort_key"].isin(ema_keys)].copy()
    df_year = df[df["sort_key"].isin(year_keys)].copy()
    df_latest = df[df["sort_key"] == latest_key].copy()

    # ── Ventas semanales por artículo (sum entre tiendas) ───────────────────
    weekly = (
        df_ema
        .groupby(["cod_articulo", "nombre_articulo", "marca", "sort_key"])["ventas_netas"]
        .sum()
        .reset_index()
    )

    # Lista ordenada de sort_keys para la ventana EMA
    ema_key_list = list(ema_weeks["sort_key"])

    # ── EMA por artículo ─────────────────────────────────────────────────────
    ema_rows: List[Dict] = []
    for (cod, nombre, marca), grp in weekly.groupby(
        ["cod_articulo", "nombre_articulo", "marca"]
    ):
        sales_map = dict(zip(grp["sort_key"], grp["ventas_netas"]))
        series = np.array([sales_map.get(k, 0.0) for k in ema_key_list], dtype=float)
        ema_rows.append(
            {"cod_articulo": cod, "nombre_articulo": nombre, "marca": marca,
             "ema": compute_ema(series)}
        )

    if not ema_rows:
        return pd.DataFrame()

    result = pd.DataFrame(ema_rows)

    # ── Ventas específicas por semana ────────────────────────────────────────
    def week_sales_map(año_int: Optional[int], sem_int: Optional[int]) -> pd.Series:
        if año_int is None:
            return pd.Series(dtype=float)
        key = int(año_int) * 100 + int(sem_int)
        sub = df[df["sort_key"] == key]
        return sub.groupby("cod_articulo")["ventas_netas"].sum()

    sem_now_map = week_sales_map(latest_año, latest_sem)
    sem_m1_map = week_sales_map(
        int(wm1["año"]) if wm1 is not None else None,
        int(wm1["semana"]) if wm1 is not None else None,
    )
    sem_m2_map = week_sales_map(
        int(wm2["año"]) if wm2 is not None else None,
        int(wm2["semana"]) if wm2 is not None else None,
    )

    result["sem_actual"] = result["cod_articulo"].map(sem_now_map).fillna(0)
    result["sem_m1"] = result["cod_articulo"].map(sem_m1_map).fillna(0)
    result["sem_m2"] = result["cod_articulo"].map(sem_m2_map).fillna(0)

    # Stock en semanas previas (para mostrar entre paréntesis junto a ventas)
    def week_stock_map(año_int: Optional[int], sem_int: Optional[int]) -> pd.Series:
        if año_int is None:
            return pd.Series(dtype=float)
        key = int(año_int) * 100 + int(sem_int)
        sub = df[df["sort_key"] == key]
        return sub.groupby("cod_articulo")["stock"].sum()

    result["stock_m1"] = result["cod_articulo"].map(week_stock_map(
        int(wm1["año"]) if wm1 is not None else None,
        int(wm1["semana"]) if wm1 is not None else None,
    )).fillna(0)
    result["stock_m2"] = result["cod_articulo"].map(week_stock_map(
        int(wm2["año"]) if wm2 is not None else None,
        int(wm2["semana"]) if wm2 is not None else None,
    )).fillna(0)

    # ── Ventas anuales y valor ───────────────────────────────────────────────
    annual_sales = df_year.groupby("cod_articulo")["ventas_netas"].sum()
    annual_valor = df_year.groupby("cod_articulo")["valor"].sum()
    result["ventas_anual"] = result["cod_articulo"].map(annual_sales).fillna(0)
    result["valor_anual"] = result["cod_articulo"].map(annual_valor).fillna(0)

    # ── Stock última semana ──────────────────────────────────────────────────
    stock_now = df_latest.groupby("cod_articulo")["stock"].sum()
    result["stock_actual"] = result["cod_articulo"].map(stock_now).fillna(0)

    # ── Semanas de stock ─────────────────────────────────────────────────────
    result["semanas_stock"] = np.where(
        result["ema"] > 0,
        result["stock_actual"] / result["ema"],
        np.nan,
    )

    # ── Alertas ─────────────────────────────────────────────────────────────
    def classify_alert(row) -> Tuple[str, str]:
        ss = row["semanas_stock"]
        if pd.isna(ss):
            return "Sin rotación", "#6b7280"
        dif = ss - semanas_objetivo
        if abs(dif) <= 1:
            return "OK", "#00c48c"
        elif abs(dif) <= 3:
            return "Riesgo", "#ffb300"
        elif dif <= -4:
            return "Falta", "#ff5252"
        else:
            return "Sobrestock", "#9c27b0"

    alerts = result.apply(classify_alert, axis=1)
    result["alerta"] = alerts.apply(lambda x: x[0])
    result["alerta_color"] = alerts.apply(lambda x: x[1])

    # ── Cobertura y unidades por tienda ─────────────────────────────────────
    total_stores = df.groupby("cod_articulo")["nombre_tienda"].nunique()
    stores_with_stock = (
        df_latest[df_latest["stock"] > 0]
        .groupby("cod_articulo")["nombre_tienda"]
        .nunique()
    )
    result["total_tiendas"] = result["cod_articulo"].map(total_stores).fillna(0)
    result["tiendas_con_stock"] = result["cod_articulo"].map(stores_with_stock).fillna(0)

    result["cobertura_pct"] = np.where(
        result["total_tiendas"] > 0,
        (result["tiendas_con_stock"] / result["total_tiendas"] * 100).round(1),
        0.0,
    )
    result["ud_por_tienda"] = np.where(
        result["total_tiendas"] > 0,
        (result["stock_actual"] / result["total_tiendas"]).round(2),
        0.0,
    )

    # ── Redondeos finales ────────────────────────────────────────────────────
    result["ema"] = result["ema"].round(1)
    result["sem_actual"] = result["sem_actual"].round(1)
    result["sem_m1"] = result["sem_m1"].round(1)
    result["sem_m2"] = result["sem_m2"].round(1)
    result["ventas_anual"] = result["ventas_anual"].round(0)
    result["valor_anual"] = result["valor_anual"].round(0)
    result["stock_actual"] = result["stock_actual"].round(0)
    result["semanas_stock"] = result["semanas_stock"].round(1)
    result["stock_m1"] = result["stock_m1"].round(0)
    result["stock_m2"] = result["stock_m2"].round(0)

    return result.reset_index(drop=True)


# ─── KPIs enriquecidos con categoría y familia ────────────────────────────────

def enrich_with_masters(
    kpis: pd.DataFrame,
    cat_art: List[Dict],
    familia_art: List[Dict],
    categorias: List[Dict],
    familias: List[Dict],
) -> pd.DataFrame:
    """Añade categoria_principal y familia a cada artículo del DataFrame KPI."""
    if kpis.empty:
        return kpis

    # Mapa categoria_id → nombre o cod_categoria y cliente
    cat_map_nombre = {c["_id"]: c.get("nombre", c["_id"]) for c in categorias}
    cat_map_cliente = {c["_id"]: c.get("cliente", "") for c in categorias}
    fam_map = {f["_id"]: {"nombre": f.get("nombre", f["_id"]), "marca": f.get("marca", "")}
               for f in familias}

    # artículo → categoría principal y cliente
    cat_art_df = pd.DataFrame(cat_art) if cat_art else pd.DataFrame()
    art_cat: Dict[str, str] = {}
    art_cliente: Dict[str, str] = {}
    if not cat_art_df.empty and "cod_articulo" in cat_art_df.columns:
        for _, row in cat_art_df.iterrows():
            cat_id = row.get("categoria_id", "")
            art_cat[row["cod_articulo"]] = cat_map_nombre.get(cat_id, cat_id)
            art_cliente[row["cod_articulo"]] = cat_map_cliente.get(cat_id, "")

    # artículo → familia
    fam_art_df = pd.DataFrame(familia_art) if familia_art else pd.DataFrame()
    art_fam: Dict[str, str] = {}
    if not fam_art_df.empty and "cod_articulo" in fam_art_df.columns:
        for _, row in fam_art_df.iterrows():
            fid = row.get("familia_id", "")
            art_fam[row["cod_articulo"]] = fam_map.get(fid, {}).get("nombre", fid)

    kpis = kpis.copy()
    kpis["categoria"] = kpis["cod_articulo"].map(art_cat).fillna("Sin categoría")
    kpis["familia"] = kpis["cod_articulo"].map(art_fam).fillna("Sin familia")
    kpis["art_cliente"] = kpis["cod_articulo"].map(art_cliente).fillna("")

    return kpis

def format_df_for_obligatoriedad(df: pd.DataFrame) -> pd.DataFrame:
    """Enriquece el DF raw con la obligatoriedad (Misma o inferior <= vs Superior >)."""
    if df.empty:
        return df
        
    db = __import__("core.firestore").firestore
    categorias = db.load_collection("categorias")
    asig_t = db.load_collection("asignaciones_cat_tienda")
    asig_a = db.load_collection("asignaciones_cat_articulo")
    
    cat_cod_map = {}
    for c in categorias:
        try:
            val = int(c.get("cod_categoria", 0))
        except:
            val = 999
        cat_cod_map[c["_id"]] = val
        
    tienda_cat_id = {a.get("nombre_tienda", ""): a.get("categoria_id", "") for a in asig_t}
    art_cat_id = {a.get("cod_articulo", ""): a.get("categoria_id", "") for a in asig_a}
    
    tienda_cod = {t: cat_cod_map.get(cid, 999) for t, cid in tienda_cat_id.items()}
    art_cod = {a: cat_cod_map.get(cid, 999) for a, cid in art_cat_id.items()}
    
    df = df.copy()
    df["_cod_cat_tienda"] = df["nombre_tienda"].map(tienda_cod).fillna(999)
    df["_cod_cat_articulo"] = df["cod_articulo"].map(art_cod).fillna(999)
    # Tabla 1: obligatorios (<=)
    # Tabla 2: opcionales (superior)
    df["_es_obligatorio"] = df["_cod_cat_articulo"] <= df["_cod_cat_tienda"]
    return df



# ─── Aggregation helpers ─────────────────────────────────────────────────────

AGG_COLS = ["ema", "sem_actual", "sem_m1", "sem_m2", "ventas_anual",
            "valor_anual", "stock_actual"]


def aggregate_kpis(kpis: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Agrega KPIs por una columna (familia, cliente, tienda…).
    Métricas de suma: ventas, stock. EMA: suma de EMAs del grupo.
    Semanas stock, cobertura, Ud/tienda: recalculadas del agregado.
    """
    if kpis.empty:
        return kpis

    agg = kpis.groupby(group_col, as_index=False).agg(
        ema=("ema", "sum"),
        sem_actual=("sem_actual", "sum"),
        sem_m1=("sem_m1", "sum"),
        sem_m2=("sem_m2", "sum"),
        ventas_anual=("ventas_anual", "sum"),
        valor_anual=("valor_anual", "sum"),
        stock_actual=("stock_actual", "sum"),
        total_tiendas=("total_tiendas", "max"),
        tiendas_con_stock=("tiendas_con_stock", "max"),
    )
    return agg


# ─── Dashboard helpers ────────────────────────────────────────────────────────

def top_tiendas(df: pd.DataFrame, n: int = 15) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Top N tiendas por unidades y valor (últimas 16 semanas)."""
    all_weeks = get_sorted_weeks(df)
    ema_keys = set(all_weeks.tail(N_WEEKS_EMA)["sort_key"])
    sub = df[df["sort_key"].isin(ema_keys)]

    by_units = (
        sub.groupby("nombre_tienda")["ventas_netas"]
        .sum().nlargest(n).reset_index()
        .rename(columns={"ventas_netas": "unidades"})
    )
    by_valor = (
        sub.groupby("nombre_tienda")["valor"]
        .sum().nlargest(n).reset_index()
        .rename(columns={"valor": "valor_total"})
    )
    return by_units, by_valor


def top_familias(df: pd.DataFrame, familias_art: List[Dict],
                 familias: List[Dict], n: int = 15) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Top N familias por unidades y valor (últimas 16 semanas)."""
    all_weeks = get_sorted_weeks(df)
    ema_keys = set(all_weeks.tail(N_WEEKS_EMA)["sort_key"])
    sub = df[df["sort_key"].isin(ema_keys)].copy()

    # Join familia
    fam_map_raw = {f["_id"]: f.get("nombre", f["_id"]) for f in familias}
    art_fam: Dict[str, str] = {}
    for r in familias_art:
        art_fam[r.get("cod_articulo", "")] = fam_map_raw.get(r.get("familia_id", ""), "Sin familia")
    sub["familia"] = sub["cod_articulo"].map(art_fam).fillna("Sin familia")

    by_units = (
        sub.groupby("familia")["ventas_netas"]
        .sum().nlargest(n).reset_index()
        .rename(columns={"ventas_netas": "unidades"})
    )
    by_valor = (
        sub.groupby("familia")["valor"]
        .sum().nlargest(n).reset_index()
        .rename(columns={"valor": "valor_total"})
    )
    return by_units, by_valor


def top_categorias(df: pd.DataFrame, cat_tienda: List[Dict],
                   categorias: List[Dict], n: int = 15) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Top N categorías de tienda por unidades y valor (últimas 16 semanas)."""
    all_weeks = get_sorted_weeks(df)
    ema_keys = set(all_weeks.tail(N_WEEKS_EMA)["sort_key"])
    sub = df[df["sort_key"].isin(ema_keys)].copy()

    cat_map = {c["_id"]: c.get("nombre", c["_id"]) for c in categorias}
    # tienda → categoría principal
    tienda_cat: Dict[str, str] = {}
    for r in cat_tienda:
        if r.get("es_principal"):
            tienda_cat[r.get("nombre_tienda", "")] = cat_map.get(r.get("categoria_id", ""), "Sin categoría")

    sub["cat_tienda"] = sub["nombre_tienda"].map(tienda_cat).fillna("Sin categoría")

    by_units = (
        sub.groupby("cat_tienda")["ventas_netas"]
        .sum().nlargest(n).reset_index()
        .rename(columns={"ventas_netas": "unidades", "cat_tienda": "categoria"})
    )
    by_valor = (
        sub.groupby("cat_tienda")["valor"]
        .sum().nlargest(n).reset_index()
        .rename(columns={"valor": "valor_total", "cat_tienda": "categoria"})
    )
    return by_units, by_valor


def alarmas(kpis: pd.DataFrame, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Genera las tres tablas de alarmas para el dashboard."""
    all_weeks = get_sorted_weeks(df)

    # 1. Tiendas con menor semanas de stock
    all_keys = set(all_weeks.tail(N_WEEKS_EMA)["sort_key"])
    sub = df[df["sort_key"].isin(all_keys)]
    latest_key = int(all_weeks.iloc[-1]["sort_key"]) if not all_weeks.empty else 0
    df_latest = df[df["sort_key"] == latest_key]

    stock_tienda = df_latest.groupby("nombre_tienda")["stock"].sum()
    ema_tienda = (
        sub.groupby(["nombre_tienda", "sort_key"])["ventas_netas"].sum()
        .reset_index()
    )
    ema_tienda_agg: Dict[str, float] = {}
    ema_key_list = list(all_weeks.tail(N_WEEKS_EMA)["sort_key"])
    for tienda, grp in ema_tienda.groupby("nombre_tienda"):
        sales_map = dict(zip(grp["sort_key"], grp["ventas_netas"]))
        series = np.array([sales_map.get(k, 0.0) for k in ema_key_list])
        ema_tienda_agg[tienda] = compute_ema(series)

    rows_tiendas = []
    for tienda, stock in stock_tienda.items():
        ema_val = ema_tienda_agg.get(tienda, 0)
        ss = (stock / ema_val) if ema_val > 0 else None
        rows_tiendas.append({"Tienda": tienda, "Stock": round(stock, 0),
                              "Semanas Stock": round(ss, 1) if ss else None})
    low_stock = (
        pd.DataFrame(rows_tiendas)
        .dropna(subset=["Semanas Stock"])
        .nsmallest(15, "Semanas Stock")
    )

    # 2. Artículos sin movimiento (más semanas consecutivas sin ventas)
    ema_keys_set = set(all_weeks.tail(N_WEEKS_EMA)["sort_key"])
    art_weekly = (
        df[df["sort_key"].isin(ema_keys_set)]
        .groupby(["cod_articulo", "nombre_articulo", "sort_key"])["ventas_netas"]
        .sum().reset_index()
    )
    max_zeros: Dict[str, int] = {}
    for (cod, nom), grp in art_weekly.groupby(["cod_articulo", "nombre_articulo"]):
        sales_map = dict(zip(grp["sort_key"], grp["ventas_netas"]))
        streak = 0
        max_streak = 0
        for k in reversed(ema_key_list):
            if sales_map.get(k, 0) == 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                break
        max_zeros[cod] = max_streak

    no_mov = (
        kpis[["cod_articulo", "nombre_articulo", "marca", "stock_actual"]]
        .copy()
    )
    no_mov["sem_sin_venta"] = no_mov["cod_articulo"].map(max_zeros).fillna(0).astype(int)
    no_mov = no_mov[no_mov["sem_sin_venta"] > 0].nlargest(15, "sem_sin_venta")
    no_mov = no_mov.rename(columns={
        "nombre_articulo": "Artículo", "marca": "Marca",
        "stock_actual": "Stock", "sem_sin_venta": "Sem. sin venta"
    })

    # 3. Artículos con bajo stock relativo (alerta Falta)
    bajo_stock = kpis[kpis["alerta"] == "Falta"].nsmallest(15, "semanas_stock")[
        ["nombre_articulo", "marca", "ema", "stock_actual", "semanas_stock", "alerta_color"]
    ].rename(columns={
        "nombre_articulo": "Artículo", "marca": "Marca",
        "ema": "Prom. EMA", "stock_actual": "Stock", "semanas_stock": "Sem. Stock"
    })

    return {
        "low_stock_tiendas": low_stock,
        "no_movimiento": no_mov,
        "bajo_stock_art": bajo_stock,
    }


# ─── KPIs por Tienda ──────────────────────────────────────────────────────────

def compute_store_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """KPIs a nivel de tienda: EMA, sem_m2, sem_m1, sem_actual, ventas_anual, stock_actual."""
    if df.empty:
        return pd.DataFrame()

    all_weeks = get_sorted_weeks(df)
    if all_weeks.empty:
        return pd.DataFrame()

    ema_weeks = all_weeks.tail(N_WEEKS_EMA)
    ema_key_list = list(ema_weeks["sort_key"])
    ema_keys = set(ema_key_list)
    year_keys = set(all_weeks.tail(N_WEEKS_YEAR)["sort_key"])
    latest = all_weeks.iloc[-1]
    wm1 = all_weeks.iloc[-2] if len(all_weeks) >= 2 else None
    wm2 = all_weeks.iloc[-3] if len(all_weeks) >= 3 else None
    latest_key = int(latest["sort_key"])

    df_ema = df[df["sort_key"].isin(ema_keys)]
    df_year = df[df["sort_key"].isin(year_keys)]
    df_latest = df[df["sort_key"] == latest_key]

    tienda_cliente = (
        df.groupby("nombre_tienda")["nombre_cliente"]
        .agg(lambda s: s.mode()[0] if not s.empty else "—")
    )

    weekly = (
        df_ema.groupby(["nombre_tienda", "sort_key"])["ventas_netas"]
        .sum().reset_index()
    )

    ema_rows = []
    for tienda, grp in weekly.groupby("nombre_tienda"):
        sales_map = dict(zip(grp["sort_key"], grp["ventas_netas"]))
        series = np.array([sales_map.get(k, 0.0) for k in ema_key_list], dtype=float)
        ema_rows.append({
            "nombre_tienda": tienda,
            "nombre_cliente": tienda_cliente.get(tienda, "—"),
            "ema": round(compute_ema(series), 1),
        })

    if not ema_rows:
        return pd.DataFrame()

    result = pd.DataFrame(ema_rows)

    def week_sales_tienda(week_row):
        if week_row is None:
            return pd.Series(dtype=float)
        key = int(week_row["sort_key"])
        return df[df["sort_key"] == key].groupby("nombre_tienda")["ventas_netas"].sum()

    result["sem_actual"] = result["nombre_tienda"].map(week_sales_tienda(latest)).fillna(0).round(1)
    result["sem_m1"] = result["nombre_tienda"].map(week_sales_tienda(wm1)).fillna(0).round(1)
    result["sem_m2"] = result["nombre_tienda"].map(week_sales_tienda(wm2)).fillna(0).round(1)
    result["ventas_anual"] = result["nombre_tienda"].map(
        df_year.groupby("nombre_tienda")["ventas_netas"].sum()
    ).fillna(0).round(0)
    result["stock_actual"] = result["nombre_tienda"].map(
        df_latest.groupby("nombre_tienda")["stock"].sum()
    ).fillna(0).round(0)

    return result.reset_index(drop=True)


def compute_article_store_kpis(df: pd.DataFrame, semanas_obj: int = 8) -> pd.DataFrame:
    """KPIs a nivel de (tienda, artículo). Incluye artículos con stock aunque no haya ventas."""
    if df.empty:
        return pd.DataFrame()

    all_weeks = get_sorted_weeks(df)
    if all_weeks.empty:
        return pd.DataFrame()

    ema_weeks = all_weeks.tail(N_WEEKS_EMA)
    ema_key_list = list(ema_weeks["sort_key"])
    ema_keys = set(ema_key_list)
    year_keys = set(all_weeks.tail(N_WEEKS_YEAR)["sort_key"])
    latest = all_weeks.iloc[-1]
    wm1 = all_weeks.iloc[-2] if len(all_weeks) >= 2 else None
    wm2 = all_weeks.iloc[-3] if len(all_weeks) >= 3 else None
    latest_key = int(latest["sort_key"])

    df_ema = df[df["sort_key"].isin(ema_keys)]
    df_year = df[df["sort_key"].isin(year_keys)]
    df_latest = df[df["sort_key"] == latest_key]

    art_meta = (
        df.groupby("cod_articulo")
        .agg(nombre_articulo=("nombre_articulo", "first"), marca=("marca", "first"))
        .to_dict("index")
    )

    weekly = (
        df_ema.groupby(["nombre_tienda", "cod_articulo", "sort_key"])["ventas_netas"]
        .sum().reset_index()
    )

    ema_rows: List[Dict] = []
    for (tienda, cod), grp in weekly.groupby(["nombre_tienda", "cod_articulo"]):
        sales_map = dict(zip(grp["sort_key"], grp["ventas_netas"]))
        series = np.array([sales_map.get(k, 0.0) for k in ema_key_list], dtype=float)
        meta = art_meta.get(cod, {"nombre_articulo": cod, "marca": "—"})
        ema_rows.append({
            "nombre_tienda": tienda,
            "cod_articulo": cod,
            "nombre_articulo": meta["nombre_articulo"],
            "marca": meta["marca"],
            "ema": compute_ema(series),
        })

    result = pd.DataFrame(ema_rows) if ema_rows else pd.DataFrame(
        columns=["nombre_tienda", "cod_articulo", "nombre_articulo", "marca", "ema"]
    )

    # Incluir artículos solo con stock (sin ventas en ventana EMA)
    df_stock_latest = (
        df_latest[df_latest["stock"] > 0]
        [["nombre_tienda", "cod_articulo", "nombre_articulo", "marca"]]
        .drop_duplicates(subset=["nombre_tienda", "cod_articulo"])
    )

    if not df_stock_latest.empty:
        if not result.empty:
            merged = df_stock_latest.merge(
                result[["nombre_tienda", "cod_articulo"]].assign(_exists=True),
                on=["nombre_tienda", "cod_articulo"], how="left"
            )
            df_stock_only = merged[merged["_exists"].isna()].drop(columns=["_exists"])
        else:
            df_stock_only = df_stock_latest.copy()

        if not df_stock_only.empty:
            df_stock_only = df_stock_only.copy()
            df_stock_only["ema"] = 0.0
            result = pd.concat([result, df_stock_only], ignore_index=True)

    if result.empty:
        return pd.DataFrame()

    # Ventas semanales específicas (merge)
    def week_df(week_row, col_name):
        if week_row is None:
            return pd.DataFrame(columns=["nombre_tienda", "cod_articulo", col_name])
        key = int(week_row["sort_key"])
        agg = (
            df[df["sort_key"] == key]
            .groupby(["nombre_tienda", "cod_articulo"])["ventas_netas"]
            .sum().reset_index().rename(columns={"ventas_netas": col_name})
        )
        return agg

    result = result.merge(week_df(latest, "sem_actual"), on=["nombre_tienda", "cod_articulo"], how="left")
    result = result.merge(week_df(wm1, "sem_m1"), on=["nombre_tienda", "cod_articulo"], how="left")
    result = result.merge(week_df(wm2, "sem_m2"), on=["nombre_tienda", "cod_articulo"], how="left")

    # Stock en semanas -1 y -2 (para mostrar junto a ventas entre paréntesis)
    def week_stock_df(week_row, col_name):
        if week_row is None:
            return pd.DataFrame(columns=["nombre_tienda", "cod_articulo", col_name])
        key = int(week_row["sort_key"])
        agg = (
            df[df["sort_key"] == key]
            .groupby(["nombre_tienda", "cod_articulo"])["stock"]
            .sum().reset_index().rename(columns={"stock": col_name})
        )
        return agg

    result = result.merge(week_stock_df(wm1, "stock_m1"), on=["nombre_tienda", "cod_articulo"], how="left")
    result = result.merge(week_stock_df(wm2, "stock_m2"), on=["nombre_tienda", "cod_articulo"], how="left")

    annual = (
        df_year.groupby(["nombre_tienda", "cod_articulo"])["ventas_netas"]
        .sum().reset_index().rename(columns={"ventas_netas": "ventas_anual"})
    )
    result = result.merge(annual, on=["nombre_tienda", "cod_articulo"], how="left")

    stock_agg = (
        df_latest.groupby(["nombre_tienda", "cod_articulo"])["stock"]
        .sum().reset_index().rename(columns={"stock": "stock_actual"})
    )
    result = result.merge(stock_agg, on=["nombre_tienda", "cod_articulo"], how="left")

    for col in ["sem_actual", "sem_m1", "sem_m2", "ventas_anual", "stock_actual", "stock_m1", "stock_m2"]:
        result[col] = result[col].fillna(0)

    # Semanas de stock
    result["semanas_stock"] = np.where(
        result["ema"] > 0,
        result["stock_actual"] / result["ema"],
        np.nan,
    )

    # Alertas
    def classify_alert_store(row):
        ss = row["semanas_stock"]
        if pd.isna(ss):
            return "Sin rotación"
        dif = ss - semanas_obj
        if abs(dif) <= 1:
            return "OK"
        elif abs(dif) <= 3:
            return "Riesgo"
        elif dif <= -4:
            return "Falta"
        else:
            return "Sobrestock"

    result["alerta"] = result.apply(classify_alert_store, axis=1)

    for col in ["ema", "sem_actual", "sem_m1", "sem_m2", "ventas_anual", "stock_actual"]:
        result[col] = result[col].round(1)
    result["semanas_stock"] = result["semanas_stock"].round(1)
    result["stock_m1"] = result["stock_m1"].round(0)
    result["stock_m2"] = result["stock_m2"].round(0)

    return result.reset_index(drop=True)
