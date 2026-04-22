"""inputs/validator.py — Validación y upsert a Firestore por tipo de input."""
import streamlit as st
import pandas as pd
import uuid
from typing import Dict, List, Tuple

from core import firestore as db
from inputs.uploader import INPUT_SCHEMAS


def _clean_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
    return df


def _clean_str(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


# ─── EDI Semanal ──────────────────────────────────────────────────────────────

def process_edi(df: pd.DataFrame) -> Dict:
    """Valida y hace upsert de registros EDI agrupando por (año, semana)."""
    required = list(INPUT_SCHEMAS["EDI Semanal"]["required"].keys())
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        return {"error": f"Columnas faltantes: {missing_cols}"}

    df = _clean_numeric(df, ["año", "semana", "ventas", "devoluciones", "stock"])
    df = _clean_str(df, ["cod_cliente", "nombre_cliente", "marca",
                          "nombre_tienda", "cod_articulo", "nombre_articulo"])

    df["año"] = df["año"].astype(int)
    df["semana"] = df["semana"].astype(int)

    # Eliminar filas con clave nula
    df = df.dropna(subset=["año", "semana", "nombre_tienda", "cod_articulo"])
    if df.empty:
        return {"error": "No hay filas válidas tras la validación."}

    # Crear maestros automáticamente
    with st.spinner("Creando maestros (clientes, tiendas, artículos)…"):
        db.ensure_masters(df.to_dict("records"))

    # Agrupar y hacer upsert por (año, semana, cod_cliente)
    # Particionado por cliente para evitar superar el límite 1MB/doc de Firestore
    total_ins = total_rep = 0
    groups = df.groupby(["año", "semana", "cod_cliente"])
    progress = st.progress(0, text="Subiendo datos…")
    n_groups = len(groups)

    for i, ((año, semana, cod_cliente), grp) in enumerate(groups):
        records = grp.to_dict("records")
        result = db.upsert_edi_week(int(año), int(semana), str(cod_cliente), records)
        total_ins += result["insertados"]
        total_rep += result["reemplazados"]
        progress.progress((i + 1) / n_groups,
                          text=f"Sem {int(semana)}/{int(año)} · Cliente {cod_cliente}…")

    progress.empty()
    db.invalidate_cache()
    return {"insertados": total_ins, "reemplazados": total_rep, "semanas": n_groups}


# ─── Precios ──────────────────────────────────────────────────────────────────

def process_precios(df: pd.DataFrame) -> Dict:
    if "cod_articulo" not in df.columns or "precio" not in df.columns:
        return {"error": "Se requieren columnas: cod_articulo, precio"}

    df = _clean_str(df, ["cod_articulo"])
    df = _clean_numeric(df, ["precio"])
    df = df.dropna(subset=["cod_articulo"])
    df = df[df["cod_articulo"].str.strip() != ""]

    insertados = reemplazados = 0
    for _, row in df.iterrows():
        cod = str(row["cod_articulo"]).strip()
        existing = db.get_doc("precios", cod)
        data = {"cod_articulo": cod, "precio": float(row.get("precio", 0))}
        if "nombre_articulo" in row and pd.notna(row["nombre_articulo"]):
            data["nombre_articulo"] = str(row["nombre_articulo"]).strip()
        if "marca" in row and pd.notna(row["marca"]):
            data["marca"] = str(row["marca"]).strip()
        db.upsert_doc("precios", cod, data)
        if existing:
            reemplazados += 1
        else:
            insertados += 1

    db.invalidate_cache()
    return {"insertados": insertados, "reemplazados": reemplazados}


# ─── Categorías Tiendas ───────────────────────────────────────────────────────

def process_cat_tiendas(df: pd.DataFrame, create_missing: bool = False, skip_missing: bool = False) -> Dict:
    required = list(INPUT_SCHEMAS["Categorías tiendas"]["required"].keys())
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        return {"error": f"Columnas faltantes: {missing_cols}"}

    df = _clean_str(df, ["nombre_tienda", "cod_categoria", "cliente", "nombre_categoria"])
    df = df.dropna(subset=["nombre_tienda", "cod_categoria"])
    
    # Check against existing
    tiendas = db.load_collection("tiendas")
    tienda_to_client = {t.get("nombre", ""): t.get("nombre_cliente", "") for t in tiendas}
    
    existing_cats = db.load_collection("categorias")
    # key: f"{cliente_name}_{cod_categoria}" -> _id
    cat_map = {
        f"{c.get('cliente', '').lower()}_{str(c.get('cod_categoria', '')).lower()}": c["_id"]
        for c in existing_cats
    }
    
    missing_cats = []
    
    for _, row in df.iterrows():
        t = str(row["nombre_tienda"]).strip()
        cod = str(row["cod_categoria"]).strip()
        cli = str(row.get("cliente", "")).strip() or tienda_to_client.get(t, "")
        
        if not cli:
            continue # Can't determine client
            
        key = f"{cli.lower()}_{cod.lower()}"
        if key not in cat_map:
            missing_cats.append({
                "cod_categoria": cod,
                "cliente": cli,
                "nombre_categoria": str(row.get("nombre_categoria", "")).strip() or f"Cat {cod}"
            })
            
    # Remove duplicates in missing
    unique_missing = {}
    for m in missing_cats:
        k = f"{m['cliente'].lower()}_{m['cod_categoria'].lower()}"
        unique_missing[k] = m
    missing_cats = list(unique_missing.values())
    
    if missing_cats and not create_missing and not skip_missing:
        return {"missing_categories": missing_cats}
        
    if create_missing and missing_cats:
        for m in missing_cats:
            new_id = str(uuid.uuid4())[:8]
            data = {"cliente": m["cliente"], "cod_categoria": m["cod_categoria"], "nombre": m["nombre_categoria"], "color": "#4f8ef7"}
            db.upsert_doc("categorias", new_id, data)
            cat_map[f"{m['cliente'].lower()}_{m['cod_categoria'].lower()}"] = new_id

    # Now assign
    asignaciones = db.load_collection("asignaciones_cat_tienda")
    asignaciones_map = {a.get("nombre_tienda", ""): a["_id"] for a in asignaciones}
    
    insertados = reemplazados = omitidos = 0
    for _, row in df.iterrows():
        t = str(row["nombre_tienda"]).strip()
        cod = str(row["cod_categoria"]).strip()
        cli = str(row.get("cliente", "")).strip() or tienda_to_client.get(t, "")
        
        if not cli:
            omitidos += 1
            continue
            
        key = f"{cli.lower()}_{cod.lower()}"
        cid = cat_map.get(key)
        
        if not cid:
            omitidos += 1
            continue
            
        data = {
            "nombre_tienda": t,
            "categoria_id": cid,
            "tipo": "importacion"
        }
        
        if t in asignaciones_map:
            db.upsert_doc("asignaciones_cat_tienda", asignaciones_map[t], data)
            reemplazados += 1
        else:
            new_id = str(uuid.uuid4())[:8]
            db.upsert_doc("asignaciones_cat_tienda", new_id, data)
            asignaciones_map[t] = new_id
            insertados += 1

    db.invalidate_cache()
    res = {"insertados": insertados, "reemplazados": reemplazados}
    if omitidos > 0:
        res["omitidos"] = omitidos
    return res


# ─── Categorías Artículo ──────────────────────────────────────────────────────

def process_cat_articulos(df: pd.DataFrame, create_missing: bool = False, skip_missing: bool = False) -> Dict:
    required = list(INPUT_SCHEMAS["Categorías artículos"]["required"].keys())
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        return {"error": f"Columnas faltantes: {missing_cols}"}

    df = _clean_str(df, ["cod_articulo", "cod_categoria", "nombre_articulo", "marca", "nombre_categoria"])
    df = df.dropna(subset=["cod_articulo", "cod_categoria"])
    
    # Para conocer los clientes, necesitamos cruzar cod_articulo -> tiendas donde se vende -> cliente
    # Dado que artículo puede venderse en varias tiendas y clientes, la categoría numérica 
    # de un artículo puede ser genérica o por cliente. El usuario dijo: 
    # "Al crear una categoría se requiere un cliente". Entonces el código de categoría
    # de un artículo necesita especificar el cliente, ¿o el artículo asume el cliente según dónde se venda?
    # Para simplificar, buscaremos el código de categoría en todas las categorías. Si hay colisión de código
    # para distintos clientes, tomaremos la primera o pediremos especificar cliente.
    # Pero el input "Categorías articulos" no tiene cliente como opcional.
    # Si un artículo es global, su categoría también. Vamos a asumir que buscan el código en cualquier cliente.
    
    existing_cats = db.load_collection("categorias")
    # map by just cod_categoria since we might not know client for article mapping easily 
    # if it's unique enough or we just match the first we find
    cat_cod_map = {}
    for c in existing_cats:
        cod = str(c.get("cod_categoria", "")).lower()
        if cod not in cat_cod_map:
            cat_cod_map[cod] = []
        cat_cod_map[cod].append(c["_id"])
        
    missing_cats = []
    
    for _, row in df.iterrows():
        cod = str(row["cod_categoria"]).strip()
        if cod.lower() not in cat_cod_map:
            missing_cats.append({
                "cod_categoria": cod,
                "cliente": "Por definir", # Como no sabemos el cliente, sugerimos uno genérico
                "nombre_categoria": str(row.get("nombre_categoria", "")).strip() or f"Cat {cod}"
            })
            
    unique_missing = {m['cod_categoria'].lower(): m for m in missing_cats}
    missing_cats = list(unique_missing.values())
    
    if missing_cats and not create_missing and not skip_missing:
        return {"missing_categories": missing_cats}
        
    if create_missing and missing_cats:
        for m in missing_cats:
            new_id = str(uuid.uuid4())[:8]
            data = {"cliente": m["cliente"], "cod_categoria": m["cod_categoria"], "nombre": m["nombre_categoria"], "color": "#4f8ef7"}
            db.upsert_doc("categorias", new_id, data)
            cat_cod_map[str(m["cod_categoria"]).lower()] = [new_id]

    asignaciones = db.load_collection("asignaciones_cat_articulo")
    asignaciones_map = {a.get("cod_articulo", ""): a["_id"] for a in asignaciones}
    
    insertados = reemplazados = omitidos = 0
    for _, row in df.iterrows():
        art = str(row["cod_articulo"]).strip()
        cod = str(row["cod_categoria"]).strip()
        
        cids = cat_cod_map.get(cod.lower())
        if not cids:
            omitidos += 1
            continue
            
        cid = cids[0] # Tomamos la primera coincidencia
        
        data = {
            "cod_articulo": art,
            "categoria_id": cid,
            "tipo": "importacion"
        }
        
        if art in asignaciones_map:
            db.upsert_doc("asignaciones_cat_articulo", asignaciones_map[art], data)
            reemplazados += 1
        else:
            new_id = str(uuid.uuid4())[:8]
            db.upsert_doc("asignaciones_cat_articulo", new_id, data)
            asignaciones_map[art] = new_id
            insertados += 1

    db.invalidate_cache()
    res = {"insertados": insertados, "reemplazados": reemplazados}
    if omitidos > 0:
        res["omitidos"] = omitidos
    return res


# ─── Familias Artículo ────────────────────────────────────────────────────────

def process_fam_articulos(df: pd.DataFrame) -> Dict:
    required = list(INPUT_SCHEMAS["Familias artículos"]["required"].keys())
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        return {"error": f"Columnas faltantes: {missing_cols}"}

    df = _clean_str(df, ["cod_articulo", "nombre_familia", "nombre_articulo", "marca"])
    df = df.dropna(subset=["cod_articulo", "nombre_familia"])

    insertados = reemplazados = omitidos = 0
    
    existing_fams = db.load_collection("familias")
    fam_map = {f"{f.get('nombre','').lower()}": f["_id"] for f in existing_fams}
    
    # Create missing families automatically (as it doesn't require complex client logic)
    for _, row in df.iterrows():
        fam = str(row["nombre_familia"]).strip()
        marca = str(row.get("marca", "")).strip()
        if fam.lower() not in fam_map:
            new_id = str(uuid.uuid4())[:8]
            db.upsert_doc("familias", new_id, {"nombre": fam, "marca": marca})
            fam_map[fam.lower()] = new_id
            
    asignaciones = db.load_collection("asignaciones_familia")
    asignaciones_map = {a.get("cod_articulo", ""): a["_id"] for a in asignaciones}

    for _, row in df.iterrows():
        art = str(row["cod_articulo"]).strip()
        fam = str(row["nombre_familia"]).strip()
        
        fid = fam_map.get(fam.lower())
        if not fid:
            omitidos += 1
            continue
            
        data = {
            "cod_articulo": art,
            "familia_id": fid,
            "tipo": "importacion"
        }
        
        if art in asignaciones_map:
            db.upsert_doc("asignaciones_familia", asignaciones_map[art], data)
            reemplazados += 1
        else:
            new_id = str(uuid.uuid4())[:8]
            db.upsert_doc("asignaciones_familia", new_id, data)
            asignaciones_map[art] = new_id
            insertados += 1

    db.invalidate_cache()
    res = {"insertados": insertados, "reemplazados": reemplazados}
    if omitidos > 0:
        res["omitidos"] = omitidos
    return res


# ─── Router ───────────────────────────────────────────────────────────────────

PROCESSORS = {
    "EDI Semanal": process_edi,
    "Precios": process_precios,
    "Categorías tiendas": process_cat_tiendas,
    "Categorías artículos": process_cat_articulos,
    "Familias artículos": process_fam_articulos,
}


def run_validation(input_type: str, df: pd.DataFrame, **kwargs) -> Dict:
    """Ejecuta el procesador correspondiente al tipo de input."""
    processor = PROCESSORS.get(input_type)
    if not processor:
        return {"error": f"Tipo de input desconocido: {input_type}"}
    return processor(df, **kwargs)


def show_result(result: Dict, input_type: str):
    """Muestra el resumen del proceso de carga."""
    if "error" in result:
        st.error(f"❌ Error: {result['error']}")
        return

    ins = result.get("insertados", 0)
    rep = result.get("reemplazados", 0)
    sem = result.get("semanas", None)

    st.success("✅ Datos cargados correctamente")
    cols = st.columns(3 if sem else 2)
    with cols[0]:
        st.metric("Insertados", f"{ins:,}")
    with cols[1]:
        st.metric("Reemplazados", f"{rep:,}")
    if sem and len(cols) > 2:
        with cols[2]:
            st.metric("Semanas procesadas", f"{sem:,}")
