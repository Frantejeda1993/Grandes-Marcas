"""pages/bd.py — Gestión de datos: visualizar, editar, eliminar, exportar."""
import streamlit as st
import pandas as pd
import io

from core.firestore import (
    load_collection, upsert_doc, delete_docs_batch, invalidate_cache
)
from core.firestore import load_edi_flat
from components.kpi_cards import section_header


COLECCIONES = {
    "EDI Semanal (plano)": "__edi_flat__",
    "Precios": "precios",
    "Categorías": "categorias",
    "Familias": "familias",
    "Clientes": "clientes",
    "Marcas": "marcas",
    "Tiendas": "tiendas",
    "Artículos": "articulos",
    "Asig. Cat. Tiendas": "asignaciones_cat_tienda",
    "Asig. Familias Art.": "asignaciones_familia",
}


def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>🗄️ Base de Datos</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:20px;'>"
        "Exploración, edición manual y exportación de datos</p>",
        unsafe_allow_html=True,
    )

    # ── Selector de colección ─────────────────────────────────────────────────
    col_nombre = st.selectbox("Colección", options=list(COLECCIONES.keys()), key="bd_col_sel")
    col_key = COLECCIONES[col_nombre]

    # ── Cargar datos ──────────────────────────────────────────────────────────
    with st.spinner("Cargando…"):
        if col_key == "__edi_flat__":
            df = load_edi_flat()
            is_edi = True
        else:
            records = load_collection(col_key)
            df = pd.DataFrame(records) if records else pd.DataFrame()
            is_edi = False

    if df is None or df.empty:
        st.info(f"La colección «{col_nombre}» está vacía.")
        _render_refresh_btn()
        return

    # ── Filtros rápidos ───────────────────────────────────────────────────────
    section_header(f"{col_nombre} — {len(df):,} registros", "📋")

    search_col, export_col = st.columns([3, 1])
    with search_col:
        query = st.text_input("🔍 Buscar en cualquier campo", placeholder="Escribe para filtrar…",
                              key="bd_search")
    with export_col:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        export_btn = st.button("⬇️ Exportar CSV", width="stretch", key="btn_export_csv")

    # Aplicar búsqueda
    df_view = df.copy()
    if query:
        mask = df_view.apply(
            lambda col: col.astype(str).str.contains(query, case=False, na=False)
        ).any(axis=1)
        df_view = df_view[mask]

    st.markdown(
        f"<div style='font-size:0.8rem;color:#6b7280;margin-bottom:8px;'>"
        f"Mostrando {len(df_view):,} de {len(df):,} registros</div>",
        unsafe_allow_html=True,
    )

    # ── Exportar CSV ──────────────────────────────────────────────────────────
    if export_btn:
        csv_data = df_view.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 Descargar CSV",
            data=csv_data,
            file_name=f"{col_nombre.replace(' ', '_')}_export.csv",
            mime="text/csv",
            key="btn_download_csv",
        )

    # ── Vista y edición ───────────────────────────────────────────────────────
    if is_edi:
        # EDI es solo lectura (demasiado grande para edición directa)
        st.dataframe(df_view, width="stretch", hide_index=True, height=500)
        st.caption("⚠️ Los datos EDI se editan cargando un nuevo archivo en la sección Inputs.")
        _render_refresh_btn()
        return

    # Para colecciones pequeñas: tabla editable
    if "_id" in df_view.columns:
        id_col = "_id"
    else:
        id_col = None

    # Mostrar tabla editable (sin la columna _id)
    display_cols = [c for c in df_view.columns if c != "_id"]
    edited_df = st.data_editor(
        df_view[display_cols],
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="bd_editor",
        height=min(600, 60 + len(df_view) * 36),
    )

    col_save, col_del, col_ref = st.columns([2, 2, 1])

    with col_save:
        if st.button("💾 Guardar cambios", width="stretch", type="primary",
                     key="btn_bd_save"):
            if id_col and id_col in df_view.columns:
                saved = 0
                for i, row in edited_df.iterrows():
                    doc_id = df_view.iloc[i]["_id"] if i < len(df_view) else None
                    if doc_id:
                        data = {k: v for k, v in row.items() if not pd.isna(v) and v != ""}
                        upsert_doc(col_key, str(doc_id), data)
                        saved += 1
                invalidate_cache()
                st.success(f"✅ {saved} documentos actualizados.")
                st.rerun()
            else:
                st.warning("No se puede guardar: colección sin campo _id.")

    with col_del:
        if id_col and id_col in df_view.columns:
            ids_to_del = st.multiselect(
                "Seleccionar para eliminar (por _id)",
                options=df_view["_id"].tolist(),
                placeholder="Selecciona IDs…",
                key="bd_del_sel",
            )
            if ids_to_del:
                if st.button(f"🗑️ Eliminar {len(ids_to_del)} doc(s)",
                             width="stretch", key="btn_bd_del"):
                    delete_docs_batch(col_key, ids_to_del)
                    invalidate_cache()
                    st.success(f"✅ {len(ids_to_del)} documento(s) eliminados.")
                    st.rerun()

    with col_ref:
        _render_refresh_btn()


def _render_refresh_btn():
    if st.button("🔄 Refrescar", width="stretch", key="btn_bd_refresh"):
        invalidate_cache()
        st.rerun()
