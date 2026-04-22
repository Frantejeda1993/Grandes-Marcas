"""inputs/uploader.py — Carga de archivos Excel/CSV con mapeo de columnas."""
import streamlit as st
import pandas as pd
import io
from typing import Dict, List, Optional, Tuple


# ─── Definición de campos por tipo de input ───────────────────────────────────

INPUT_SCHEMAS = {
    "EDI Semanal": {
        "required": {
            "año": "Año",
            "semana": "Semana",
            "cod_cliente": "Cód. Cliente",
            "nombre_cliente": "Nombre Cliente",
            "marca": "Marca",
            "nombre_tienda": "Nombre Tienda",
            "cod_articulo": "Cód. Artículo",
            "nombre_articulo": "Nombre Artículo",
            "ventas": "Ventas",
            "devoluciones": "Devoluciones",
            "stock": "Stock",
        },
        "optional": {},
        "unique_key": ["año", "semana", "nombre_tienda", "cod_articulo"],
    },
    "Precios": {
        "required": {
            "cod_articulo": "Cód. Artículo",
            "precio": "Precio",
        },
        "optional": {
            "nombre_articulo": "Nombre Artículo",
            "marca": "Marca",
        },
        "unique_key": ["cod_articulo"],
    },
    "Categorías tiendas": {
        "required": {
            "nombre_tienda": "Nombre tienda",
            "cod_categoria": "Código categoría",
        },
        "optional": {
            "cliente": "Cliente",
            "nombre_categoria": "Nombre categoría",
        },
        "unique_key": ["nombre_tienda"],
    },
    "Categorías artículos": {
        "required": {
            "cod_articulo": "Código artículo",
            "cod_categoria": "Código categoría",
        },
        "optional": {
            "nombre_articulo": "Nombre artículo",
            "marca": "Marca",
            "nombre_categoria": "Nombre categoría",
        },
        "unique_key": ["cod_articulo"],
    },
    "Familias artículos": {
        "required": {
            "cod_articulo": "Código artículo",
            "nombre_familia": "Nombre familia",
        },
        "optional": {
            "nombre_articulo": "Nombre artículo",
            "marca": "Marca",
        },
        "unique_key": ["cod_articulo"],
    },
}


def read_file(uploaded_file) -> Optional[pd.DataFrame]:
    """Lee Excel o CSV y devuelve DataFrame crudo."""
    try:
        name = uploaded_file.name.lower()
        if name.endswith(".xlsx") or name.endswith(".xls"):
            return pd.read_excel(uploaded_file, engine="openpyxl", dtype=str)
        elif name.endswith(".csv"):
            raw = uploaded_file.read()
            # Detectar encoding y separador
            for enc in ["utf-8", "latin-1", "cp1252"]:
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            sep = ";" if text.count(";") > text.count(",") else ","
            return pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
        else:
            st.error("Formato no soportado. Usa .xlsx, .xls o .csv")
            return None
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return None


def column_mapper(
    df_raw: pd.DataFrame,
    schema: Dict,
    key_prefix: str = "col_map",
) -> Optional[Dict[str, str]]:
    """Renderiza la UI de mapeo de columnas. Devuelve {campo_interno: col_archivo}."""
    file_cols = list(df_raw.columns)
    required_fields = schema["required"]
    optional_fields = schema.get("optional", {})

    st.markdown(
        "<div style='font-size:0.85rem;color:#9ca3af;margin-bottom:12px;'>"
        "Mapea las columnas de tu archivo a los campos del sistema. "
        "Los campos marcados con <b style='color:#ff5252;'>*</b> son obligatorios."
        "</div>",
        unsafe_allow_html=True,
    )

    mapping: Dict[str, str] = {}
    valid = True

    # Columnas requeridas
    if required_fields:
        st.markdown("**Campos obligatorios**")
        cols = st.columns(min(3, len(required_fields)))
        for i, (field, label) in enumerate(required_fields.items()):
            with cols[i % len(cols)]:
                # Auto-detect: buscar columna con nombre similar (case-insensitive)
                auto_guess = next(
                    (c for c in file_cols if field.lower().replace("_", " ")
                     in c.lower().replace("_", " ") or c.lower() == field.lower()),
                    None,
                )
                default_idx = file_cols.index(auto_guess) + 1 if auto_guess else 0
                sel = st.selectbox(
                    f"{label} *",
                    options=["— sin mapear —"] + file_cols,
                    index=default_idx,
                    key=f"{key_prefix}_{field}",
                )
                if sel == "— sin mapear —":
                    st.caption(f"⚠️ Requerido")
                    valid = False
                else:
                    mapping[field] = sel

    # Columnas opcionales
    if optional_fields:
        with st.expander("Campos opcionales"):
            cols = st.columns(min(3, len(optional_fields)))
            for i, (field, label) in enumerate(optional_fields.items()):
                with cols[i % len(cols)]:
                    auto_guess = next(
                        (c for c in file_cols if field.lower().replace("_", " ")
                         in c.lower().replace("_", " ")),
                        None,
                    )
                    default_idx = file_cols.index(auto_guess) + 1 if auto_guess else 0
                    sel = st.selectbox(
                        label,
                        options=["— sin mapear —"] + file_cols,
                        index=default_idx,
                        key=f"{key_prefix}_opt_{field}",
                    )
                    if sel != "— sin mapear —":
                        mapping[field] = sel

    return mapping if valid else None


def apply_mapping(df_raw: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Aplica el mapeo de columnas y devuelve DF con nombres canónicos."""
    df = df_raw[[v for v in mapping.values() if v in df_raw.columns]].copy()
    reverse = {v: k for k, v in mapping.items()}
    df = df.rename(columns=reverse)
    return df


def preview_data(df: pd.DataFrame, n: int = 5):
    """Muestra una preview del DataFrame."""
    st.markdown(
        f"<div style='font-size:0.82rem;color:#6b7280;margin-bottom:6px;'>"
        f"Preview — {len(df):,} filas × {len(df.columns)} columnas</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(df.head(n), width="stretch", hide_index=True)
