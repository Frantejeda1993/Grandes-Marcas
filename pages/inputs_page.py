"""pages/inputs_page.py — Carga de datos: EDI, Precios, Categorías, Familias."""
import streamlit as st
import pandas as pd

from inputs.uploader import read_file, column_mapper, apply_mapping, preview_data, INPUT_SCHEMAS
from inputs.validator import run_validation, show_result
from components.kpi_cards import section_header


def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>📤 Inputs — Carga de datos</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:20px;'>"
        "Sube archivos Excel o CSV y mapea las columnas al sistema</p>",
        unsafe_allow_html=True,
    )

    # ── Selector de tipo ──────────────────────────────────────────────────────
    input_type = st.radio(
        "Tipo de datos",
        options=list(INPUT_SCHEMAS.keys()),
        horizontal=True,
        key="input_type_sel",
    )

    schema = INPUT_SCHEMAS[input_type]
    st.markdown("---")

    # ── Upload ────────────────────────────────────────────────────────────────
    section_header(f"Subir {input_type}", "📁")

    uploaded = st.file_uploader(
        "Arrastra tu archivo aquí o haz clic para seleccionar",
        type=["xlsx", "xls", "csv"],
        key=f"uploader_{input_type}",
        help="Soportado: Excel (.xlsx, .xls) y CSV (UTF-8 o Latin-1, separador , o ;)",
    )

    if not uploaded:
        _show_format_hint(input_type, schema)
        return

    # ── FIX 2: Caché del archivo en session_state ─────────────────────────────
    # La clave incluye nombre + tamaño para detectar cambios de archivo.
    # Esto evita re-leer el Excel/CSV en cada interacción del formulario de mapeo.
    cache_key = f"_raw_df_{input_type}_{uploaded.name}_{uploaded.size}"
    if cache_key not in st.session_state:
        with st.spinner("Leyendo archivo…"):
            df_raw = read_file(uploaded)
        if df_raw is None or df_raw.empty:
            st.error("El archivo está vacío o no pudo leerse.")
            return
        st.session_state[cache_key] = df_raw
    else:
        df_raw = st.session_state[cache_key]

    st.success(f"✅ Archivo: **{uploaded.name}** · {len(df_raw):,} filas × {len(df_raw.columns)} columnas")
    preview_data(df_raw, n=5)

    # ── Mapeo de columnas ─────────────────────────────────────────────────────
    section_header("Mapeo de columnas", "🔄")
    mapping = column_mapper(df_raw, schema, key_prefix=f"map_{input_type}")

    if mapping is None:
        st.warning("⚠️ Completa todos los campos obligatorios antes de continuar.")
        return

    # ── Preview con nombres canónicos ─────────────────────────────────────────
    df_mapped = apply_mapping(df_raw, mapping)

    with st.expander("👁️ Preview con columnas mapeadas"):
        preview_data(df_mapped, n=8)

    # ── Validación y carga ────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(
            f"<div style='padding:12px 16px;background:#1f2937;border-radius:10px;"
            f"font-size:0.85rem;color:#9ca3af;'>"
            f"Se procesarán <b style='color:#e8eaed;'>{len(df_mapped):,}</b> filas. "
            f"Los duplicados (por clave única) serán <b style='color:#ffb300;'>reemplazados</b>."
            f"</div>",
            unsafe_allow_html=True,
        )
    with col2:
        cargar = st.button(
            f"⬆️ Cargar {input_type}",
            width="stretch",
            type="primary",
            key="btn_cargar",
        )

    if cargar:
        with st.spinner(f"Procesando {len(df_mapped):,} registros…"):
            result = run_validation(input_type, df_mapped)
            
        if "missing_categories" in result:
            st.session_state[f"missing_{input_type}"] = result["missing_categories"]
            st.rerun()
        else:
            show_result(result, input_type)
            # Limpiar caché del archivo una vez cargado
            if cache_key in st.session_state:
                del st.session_state[cache_key]
                
    if f"missing_{input_type}" in st.session_state:
        missing = st.session_state[f"missing_{input_type}"]
        st.warning(f"⚠️ Se encontraron {len(missing)} categorías nuevas no registradas en la base de datos.")
        
        with st.expander("Ver categorías a crear"):
            st.json(missing)
            
        st.markdown("¿Qué deseas hacer con estas categorías?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Crearlas automáticamente", type="primary", width="stretch"):
                with st.spinner(f"Creando y asignando {len(df_mapped):,} registros…"):
                    # Pasamos un kwargs mágico o hack, en validator el kwargs es posicional (df_mapped, True, False)
                    # wait, validator router signature is just run_validation(input_type, df)
                    pass # We will need to fix this below so run_validation supports `**kwargs`
                    result = run_validation(input_type, df_mapped, create_missing=True)
                show_result(result, input_type)
                del st.session_state[f"missing_{input_type}"]
                if cache_key in st.session_state:
                    del st.session_state[cache_key]
                st.rerun()
        with c2:
            if st.button("Omitir asignación", width="stretch"):
                with st.spinner(f"Procesando {len(df_mapped):,} registros (omitiendo faltantes)…"):
                    result = run_validation(input_type, df_mapped, skip_missing=True)
                show_result(result, input_type)
                del st.session_state[f"missing_{input_type}"]
                if cache_key in st.session_state:
                    del st.session_state[cache_key]
                st.rerun()


def _show_format_hint(input_type: str, schema: dict):
    """FIX 3: HTML construido en Python — sin f-strings anidadas."""
    required = schema.get("required", {})
    optional = schema.get("optional", {})
    unique_key = schema.get("unique_key", [])

    # Construir HTML de campos requeridos
    req_items = " &nbsp;·&nbsp; ".join(
        "<code style='background:#1f2937;padding:2px 8px;border-radius:4px;"
        "color:#e8eaed;font-size:0.8rem;'>" + v + "</code>"
        for v in required.values()
    )

    # Construir HTML de campos opcionales (puede estar vacío)
    opt_block = ""
    if optional:
        opt_items = " &nbsp;·&nbsp; ".join(
            "<code style='background:#1f2937;padding:2px 8px;border-radius:4px;"
            "color:#6b7280;font-size:0.8rem;'>" + v + "</code>"
            for v in optional.values()
        )
        opt_block = (
            "<div style='font-size:0.82rem;color:#9ca3af;margin:10px 0 4px;'>"
            "<b style='color:#6b7280;'>Campos opcionales:</b><br>"
            + opt_items
            + "</div>"
        )

    key_str = " + ".join(unique_key)

    html = (
        "<div style='background:#161b27;border:1px solid #2a3148;border-radius:12px;"
        "padding:20px 24px;margin-top:16px;'>"
        "<div style='font-size:0.9rem;font-weight:700;color:#e8eaed;margin-bottom:12px;'>"
        "📋 Formato esperado: "
        "<span style='color:#4f8ef7;'>" + input_type + "</span>"
        "</div>"
        "<div style='font-size:0.82rem;color:#9ca3af;margin-bottom:4px;'>"
        "<b style='color:#ff5252;'>Campos obligatorios:</b><br>"
        + req_items
        + "</div>"
        + opt_block
        + "<div style='font-size:0.8rem;color:#6b7280;margin-top:10px;"
        "padding-top:10px;border-top:1px solid #1f2937;'>"
        "🔑 Clave única: <b style='color:#9ca3af;'>" + key_str + "</b>"
        "</div>"
        "</div>"
    )

    st.markdown(html, unsafe_allow_html=True)
