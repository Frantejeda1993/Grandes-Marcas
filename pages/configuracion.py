"""pages/configuracion.py — CRUD de categorías, familias y asignaciones."""
import streamlit as st
import uuid
import pandas as pd

from core.firestore import (
    load_collection, upsert_doc, delete_doc, invalidate_cache
)
from components.kpi_cards import section_header


def main():
    st.markdown(
        "<h1 style='font-size:1.6rem;font-weight:800;color:#e8eaed;"
        "margin-bottom:4px;'>⚙️ Configuración</h1>"
        "<p style='color:#6b7280;font-size:0.85rem;margin-bottom:20px;'>"
        "Gestión de categorías, familias y asignaciones</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "🗂️ Categorías",
        "👨‍👩‍👧 Familias",
        "🏪 Cat. → Tiendas",
        "📦 Familia → Artículos",
    ])

    with tab1:
        _tab_categorias()
    with tab2:
        _tab_familias()
    with tab3:
        _tab_asig_tiendas()
    with tab4:
        _tab_asig_articulos()


def _tab_categorias():
    section_header("Categorías", "🗂️")
    cats = load_collection("categorias")
    clientes = load_collection("clientes")
    clientes_list = sorted([c.get("nombre_cliente", "") for c in clientes if c.get("nombre_cliente")])
    df_cats = pd.DataFrame(cats) if cats else pd.DataFrame(columns=["_id", "cliente", "cod_categoria", "nombre", "color"])

    # Formulario de creación
    with st.expander("➕ Nueva categoría", expanded=False):
        with st.form("form_nueva_cat"):
            c1, c2, c3, c4 = st.columns([2, 1, 3, 1])
            with c1:
                nuevo_cliente = st.selectbox("Cliente *", options=clientes_list or ["(Sin clientes)"])
            with c2:
                nuevo_codigo = st.text_input("Código Numérico *")
            with c3:
                nuevo_nombre = st.text_input("Nombre *")
            with c4:
                nuevo_color = st.color_picker("Color", value="#4f8ef7")
            if st.form_submit_button("Crear", type="primary"):
                if nuevo_cliente and nuevo_codigo.strip() and nuevo_nombre.strip():
                    if not nuevo_codigo.strip().isdigit():
                        st.error("El código debe ser numérico.")
                    else:
                        # Buscar si ya existe este código para el cliente
                        existe = any(str(c.get("cod_categoria", "")) == nuevo_codigo.strip() and c.get("cliente") == nuevo_cliente for c in cats)
                        if existe:
                            st.error("Ese código de categoría ya existe para este cliente.")
                        else:
                            new_id = str(uuid.uuid4())[:8]
                            upsert_doc("categorias", new_id,
                                       {"cliente": nuevo_cliente, "cod_categoria": nuevo_codigo.strip(), "nombre": nuevo_nombre.strip(), "color": nuevo_color})
                            invalidate_cache()
                            st.success(f"✅ Categoría '{nuevo_nombre}' creada.")
                            st.rerun()
                else:
                    st.error("Faltan campos obligatorios.")

    # Tabla de categorías existentes
    if df_cats.empty:
        st.info("No hay categorías definidas.")
        return

    st.markdown("**Categorías existentes**")
    for cliente in sorted(df_cats["cliente"].dropna().unique()):
        st.markdown(f"**Cliente: {cliente}**")
        sub = df_cats[df_cats["cliente"] == cliente].sort_values("cod_categoria")
        for _, row in sub.iterrows():
            cat_id = row.get("_id", "")
            cod = row.get("cod_categoria", "")
            nombre = row.get("nombre", "")
            color = row.get("color", "#4f8ef7")
            
            c0, c1, c2, c3, c4 = st.columns([1, 1, 3, 1, 1])
            with c0:
                st.markdown(
                    f"<div style='width:24px;height:24px;border-radius:6px;"
                    f"background:{color};margin-top:6px;'></div>",
                    unsafe_allow_html=True,
                )
            with c1:
                st.text_input("Cód", value=cod, key=f"cat_cod_{cat_id}", disabled=True, label_visibility="collapsed")
            with c2:
                nuevo = st.text_input("Nombre", value=nombre, key=f"cat_nom_{cat_id}", label_visibility="collapsed")
            with c3:
                nc = st.color_picker("Color", value=color, key=f"cat_col_{cat_id}", label_visibility="collapsed")
            with c4:
                c_save, c_del = st.columns(2)
                with c_save:
                    if st.button("💾", key=f"cat_save_{cat_id}", help="Guardar"):
                        upsert_doc("categorias", cat_id, {"cliente": cliente, "cod_categoria": cod, "nombre": nuevo, "color": nc})
                        invalidate_cache()
                        st.rerun()
                with c_del:
                    if st.button("🗑️", key=f"cat_del_{cat_id}", help="Eliminar"):
                        delete_doc("categorias", cat_id)
                        invalidate_cache()
                        st.rerun()


# ─── Familias ─────────────────────────────────────────────────────────────────

def _tab_familias():
    section_header("Familias de Artículos", "👨‍👩‍👧")
    marcas_list = [m.get("nombre", "") for m in load_collection("marcas")]
    fams = load_collection("familias")
    df_fams = pd.DataFrame(fams) if fams else pd.DataFrame(columns=["_id", "nombre", "marca"])

    with st.expander("➕ Nueva familia", expanded=False):
        with st.form("form_nueva_fam"):
            col1, col2 = st.columns(2)
            with col1:
                fam_nombre = st.text_input("Nombre *")
            with col2:
                fam_marca = st.selectbox("Marca *", options=marcas_list or ["(sin marcas)"])
            if st.form_submit_button("Crear", type="primary"):
                if fam_nombre.strip() and fam_marca:
                    new_id = str(uuid.uuid4())[:8]
                    upsert_doc("familias", new_id,
                               {"nombre": fam_nombre.strip(), "marca": fam_marca})
                    invalidate_cache()
                    st.success(f"✅ Familia '{fam_nombre}' creada.")
                    st.rerun()
                else:
                    st.error("Nombre y marca son obligatorios.")

    if df_fams.empty:
        st.info("No hay familias definidas.")
        return

    # Agrupar por marca
    for marca in sorted(df_fams["marca"].dropna().unique()):
        st.markdown(f"**{marca}**")
        sub = df_fams[df_fams["marca"] == marca]
        for _, row in sub.iterrows():
            fid = row.get("_id", "")
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                nuevo = st.text_input("Nombre", value=row.get("nombre", ""),
                                      key=f"fam_nom_{fid}", label_visibility="collapsed")
            with col2:
                nm = st.selectbox("Marca", options=marcas_list or [marca],
                                  index=(marcas_list.index(marca) if marca in marcas_list else 0),
                                  key=f"fam_mar_{fid}", label_visibility="collapsed")
            with col3:
                cs, cd = st.columns(2)
                with cs:
                    if st.button("💾", key=f"fam_save_{fid}"):
                        upsert_doc("familias", fid, {"nombre": nuevo, "marca": nm})
                        invalidate_cache()
                        st.rerun()
                with cd:
                    if st.button("🗑️", key=f"fam_del_{fid}"):
                        delete_doc("familias", fid)
                        invalidate_cache()
                        st.rerun()


# ─── Asignación Categoría → Tiendas ───────────────────────────────────────────

def _tab_asig_tiendas():
    section_header("Asignación de Categorías a Tiendas", "🏪")
    tiendas = load_collection("tiendas")
    categorias = load_collection("categorias")
    asignaciones = load_collection("asignaciones_cat_tienda")

    if not tiendas or not categorias:
        st.info("Necesitas tiendas y categorías definidas para asignar.")
        return

    cat_opts = {f"({c.get('cliente','')}) {c.get('cod_categoria','')} - {c.get('nombre', '')}": c["_id"] for c in categorias}
    asig_map: dict = {}
    for a in asignaciones:
        t = a.get("nombre_tienda", "")
        cid = a.get("categoria_id", "")
        asig_map[t] = cid

    cat_id_to_name = {v: k for k, v in cat_opts.items()}

    with st.form("form_asig_tiendas"):
        tienda_sel = st.selectbox("Tienda", options=[t.get("nombre", "") for t in tiendas])
        
        cid_actual = asig_map.get(tienda_sel, "")
        cat_actual_name = cat_id_to_name.get(cid_actual)
        
        cats_sel = st.selectbox(
            "Categoría asignada",
            options=["(Sin Categoría)"] + list(cat_opts.keys()),
            index=(list(cat_opts.keys()).index(cat_actual_name) + 1 if cat_actual_name in cat_opts else 0)
        )
        tipo = st.radio("Tipo asignación", ["Manual", "Auto"], horizontal=True)
        if st.form_submit_button("Guardar asignación", type="primary"):
            # Eliminar asignaciones existentes para esta tienda
            for a in asignaciones:
                if a.get("nombre_tienda") == tienda_sel:
                    delete_doc("asignaciones_cat_tienda", a["_id"])
            # Crear nueva
            if cats_sel != "(Sin Categoría)":
                cid = cat_opts[cats_sel]
                new_id = str(uuid.uuid4())[:8]
                upsert_doc("asignaciones_cat_tienda", new_id, {
                    "nombre_tienda": tienda_sel,
                    "categoria_id": cid,
                    "tipo": tipo.lower(),
                })
            invalidate_cache()
            st.success(f"✅ Asignación guardada para {tienda_sel}.")
            st.rerun()

    # Vista resumen
    st.markdown("**Resumen de asignaciones**")
    rows = []
    for t in tiendas:
        tn = t.get("nombre", "")
        cat_asig = cat_id_to_name.get(asig_map.get(tn, ""), "—")
        rows.append({"Tienda": tn, "Categoría": cat_asig})
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ─── Asignación Familia → Artículos ───────────────────────────────────────────

def _tab_asig_articulos():
    section_header("Asignación de Familias a Artículos", "📦")
    articulos = load_collection("articulos")
    familias = load_collection("familias")
    asignaciones = load_collection("asignaciones_familia")

    if not articulos or not familias:
        st.info("Necesitas artículos y familias definidas.")
        return

    fam_opts = {f"{f.get('nombre','')} ({f.get('marca','')})": f["_id"] for f in familias}
    fam_id_to_name = {v: k for k, v in fam_opts.items()}
    asig_map = {a.get("cod_articulo", ""): a.get("familia_id", "") for a in asignaciones}
    asig_tipo = {a.get("cod_articulo", ""): a.get("tipo", "auto") for a in asignaciones}

    with st.form("form_asig_art"):
        art_opts = [f"{a.get('cod_articulo','')} — {a.get('nombre_articulo','')}" for a in articulos]
        art_sel_str = st.selectbox("Artículo", options=art_opts)
        cod_art = art_sel_str.split(" — ")[0].strip() if art_sel_str else ""
        fam_actual = fam_id_to_name.get(asig_map.get(cod_art, ""), "— sin familia —")
        fam_sel = st.selectbox("Familia", options=["— sin familia —"] + list(fam_opts.keys()),
                               index=(list(fam_opts.keys()).index(fam_actual) + 1
                                      if fam_actual in fam_opts else 0))
        tipo = st.radio("Tipo", ["Manual", "Auto"], horizontal=True,
                        index=0 if asig_tipo.get(cod_art, "auto") == "manual" else 1)
        if st.form_submit_button("Guardar", type="primary"):
            # Eliminar asignación anterior
            for a in asignaciones:
                if a.get("cod_articulo") == cod_art:
                    delete_doc("asignaciones_familia", a["_id"])
            if fam_sel != "— sin familia —":
                fid = fam_opts[fam_sel]
                new_id = str(uuid.uuid4())[:8]
                upsert_doc("asignaciones_familia", new_id, {
                    "cod_articulo": cod_art,
                    "familia_id": fid,
                    "tipo": tipo.lower(),
                })
            invalidate_cache()
            st.success(f"✅ Asignación guardada para {cod_art}.")
            st.rerun()

    # Resumen
    st.markdown("**Resumen de asignaciones**")
    rows = []
    for a in articulos:
        cod = a.get("cod_articulo", "")
        fid = asig_map.get(cod, "")
        rows.append({
            "Artículo": cod,
            "Nombre": a.get("nombre_articulo", ""),
            "Familia": fam_id_to_name.get(fid, "—"),
            "Tipo": asig_tipo.get(cod, "—"),
        })
    if rows:
        df_res = pd.DataFrame(rows)
        # Filtro rápido por marca
        marcas_art = sorted({a.get("marca", "") for a in articulos if a.get("marca")})
        if marcas_art:
            marca_f = st.selectbox("Filtrar por marca", ["Todas"] + marcas_art,
                                   key="asig_art_marca_filter")
            if marca_f != "Todas":
                art_marca = {a.get("cod_articulo") for a in articulos if a.get("marca") == marca_f}
                df_res = df_res[df_res["Artículo"].isin(art_marca)]
        st.dataframe(df_res, width="stretch", hide_index=True, height=400)
