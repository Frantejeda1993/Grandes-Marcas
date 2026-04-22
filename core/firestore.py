"""core/firestore.py — Cliente Firestore y operaciones CRUD con caché.

Estrategia de almacenamiento EDI:
  Un documento por (año, semana) → campo 'records' = lista de dicts.
  Así 2 años = ~104 lecturas Firestore (vs 120 000 en modelo plano).
"""
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as fs
import pandas as pd
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
import base64
import json
from pathlib import Path


def _looks_like_invalid_jwt_signature(exc: Exception) -> bool:
    """Detecta errores de credenciales revocadas/desincronizadas en runtime."""
    msg = str(exc).lower()
    return "invalid jwt signature" in msg or "invalid_grant" in msg


def _normalize_private_key(private_key: str) -> str:
    """Normaliza private_key para tolerar formatos frecuentes en Streamlit Cloud."""
    key = (private_key or "").strip().strip('"').strip("'").replace("\\r", "\r")
    # Caso 1: la clave viene con saltos escapados en una sola línea.
    if "\\n" in key:
        key = key.replace("\\n", "\n")
    # Caso 2: copiado con retornos CRLF.
    key = key.replace("\r\n", "\n").replace("\r", "\n")
    return key


def _decode_private_key_if_base64(private_key: str) -> str:
    """Decodifica private_key si viene en base64 (patrón común en CI/CD)."""
    key = _normalize_private_key(private_key)
    if "BEGIN PRIVATE KEY" in key:
        return key
    try:
        decoded = base64.b64decode(key).decode("utf-8")
    except Exception:
        return key
    decoded_key = _normalize_private_key(decoded)
    if "BEGIN PRIVATE KEY" in decoded_key:
        return decoded_key
    return key


def _validate_private_key_pem(private_key: str) -> None:
    """Valida formato PEM mínimo para fallar rápido con mensaje accionable."""
    key = _normalize_private_key(private_key)
    if "BEGIN PRIVATE KEY" not in key or "END PRIVATE KEY" not in key:
        raise RuntimeError(
            "firebase.private_key no tiene formato PEM válido. "
            "Debe incluir '-----BEGIN PRIVATE KEY-----' y '-----END PRIVATE KEY-----'."
        )


def _read_service_account_from_local_file() -> Optional[Dict[str, Any]]:
    """Fallback local para desarrollo fuera de Streamlit Cloud."""
    json_path = Path("firebase_key.json")
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_service_account_info() -> Dict[str, Any]:
    """Construye un dict válido de service account desde secretos o archivo local."""
    if "firebase" in st.secrets:
        info = dict(st.secrets["firebase"])
    else:
        info = _read_service_account_from_local_file() or {}

    if not info:
        raise RuntimeError(
            "No se encontraron credenciales Firebase en st.secrets['firebase'] ni en firebase_key.json."
        )

    if "private_key" in info:
        info["private_key"] = _decode_private_key_if_base64(info.get("private_key", ""))
        _validate_private_key_pem(info["private_key"])

    required = ["project_id", "client_email", "private_key"]
    missing = [k for k in required if not str(info.get(k, "")).strip()]
    if missing:
        raise RuntimeError(
            f"Faltan campos requeridos en credenciales Firebase: {', '.join(missing)}."
        )
    return info


def _reset_firebase_apps() -> None:
    """Elimina apps Firebase inicializadas para forzar re-autenticación."""
    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)


# ─── Inicialización ───────────────────────────────────────────────────────────

@st.cache_resource
def init_db():
    """Inicializa la app Firebase y devuelve el cliente Firestore (singleton)."""
    if not firebase_admin._apps:
        key_dict = _build_service_account_info()
        try:
            # Validación temprana de estructura y firma local.
            service_account.Credentials.from_service_account_info(key_dict)
            cred = credentials.Certificate(key_dict)
        except Exception as exc:
            raise RuntimeError(
                "Credenciales Firebase inválidas. Revisa [firebase] en .streamlit/secrets.toml"
            ) from exc
        firebase_admin.initialize_app(cred)
    try:
        return fs.client()
    except Exception as exc:
        raise RuntimeError(
            "No se pudo crear el cliente Firestore. Verifica project_id y credenciales."
        ) from exc


def get_db():
    return init_db()


# ─── Lectura cacheada (EDI) ───────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner="Cargando datos desde Firestore…")
def load_edi_flat() -> pd.DataFrame:
    """Carga toda la colección edi_semanal y la devuelve como DataFrame plano.
    Cada documento contiene semanas de registros agrupados (reduce lecturas).
    """
    db = get_db()
    try:
        docs = db.collection("edi_semanal").stream(timeout=20, retry=None)
    except Exception as exc:
        if _looks_like_invalid_jwt_signature(exc):
            # En Streamlit Cloud puede quedar un app Firebase viejo en memoria
            # (por ejemplo tras rotación de claves). Reintentar con app limpia.
            _reset_firebase_apps()
            init_db.clear()
            db = get_db()
            docs = db.collection("edi_semanal").stream(timeout=20, retry=None)
        else:
            raise RuntimeError(
                "No fue posible leer Firestore (edi_semanal). Revisa firma JWT/private_key en secrets."
            ) from exc

    records: List[Dict] = []
    try:
        for doc in docs:
            data = doc.to_dict()
            week_records = data.get("records", [])
            for r in week_records:
                r.setdefault("año", data.get("año"))
                r.setdefault("semana", data.get("semana"))
                records.append(r)
    except Exception as exc:
        raise RuntimeError(
            "Error al consultar Firestore. En Streamlit Cloud, valida que firebase.private_key conserve saltos de línea."
        ) from exc

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Tipado seguro
    for col in ["año", "semana"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["ventas", "devoluciones", "stock"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["ventas_netas"] = df.get("ventas", 0) - df.get("devoluciones", 0)
    df["sort_key"] = df["año"] * 100 + df["semana"]

    # Join de precios
    precios = load_collection("precios")
    if precios:
        pdf = pd.DataFrame(precios)[["cod_articulo", "precio"]].copy()
        pdf["precio"] = pd.to_numeric(pdf["precio"], errors="coerce").fillna(0.0)
        df = df.merge(pdf, on="cod_articulo", how="left")
    if "precio" not in df.columns:
        df["precio"] = 0.0
    df["precio"] = df["precio"].fillna(0.0)
    df["valor"] = df["ventas_netas"] * df["precio"]

    return df


# ─── Lectura cacheada (colecciones simples) ────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_collection(name: str) -> List[Dict]:
    """Carga todos los documentos de una colección como lista de dicts."""
    db = get_db()
    try:
        return [{"_id": d.id, **d.to_dict()} for d in db.collection(name).stream(timeout=20, retry=None)]
    except Exception as exc:
        if _looks_like_invalid_jwt_signature(exc):
            _reset_firebase_apps()
            init_db.clear()
            db = get_db()
            return [{"_id": d.id, **d.to_dict()} for d in db.collection(name).stream(timeout=20, retry=None)]
        raise RuntimeError(
            f"No se pudo cargar la colección '{name}' desde Firestore."
        ) from exc


# ─── Escritura EDI (upsert semanal) ────────────────────────────────────────────

def upsert_edi_week(año: int, semana: int, cod_cliente: str, new_records: List[Dict]) -> Dict:
    """Realiza upsert de registros EDI para una semana + cliente específicos.

    Particionado por cod_cliente para mantenerse bajo el límite de 1MB/doc de Firestore.
    Doc ID: {año}_{semana:02d}_{cod_cliente}
    Clave única dentro del doc: (nombre_tienda, cod_articulo).
    """
    db = get_db()
    safe_cliente = str(cod_cliente).replace("/", "_").replace(".", "_")[:40]
    doc_id = f"{año}_{semana:02d}_{safe_cliente}"
    doc_ref = db.collection("edi_semanal").document(doc_id)
    doc_snap = doc_ref.get()

    if doc_snap.exists:
        existing = doc_snap.to_dict().get("records", [])
        existing_map = {
            f"{r.get('nombre_tienda','')}|{r.get('cod_articulo','')}": r
            for r in existing
        }
        reemplazados = 0
        insertados = 0
        for r in new_records:
            k = f"{r.get('nombre_tienda','')}|{r.get('cod_articulo','')}"
            if k in existing_map:
                reemplazados += 1
            else:
                insertados += 1
            existing_map[k] = r
        updated = list(existing_map.values())
    else:
        updated = new_records
        insertados = len(new_records)
        reemplazados = 0

    doc_ref.set({"año": año, "semana": semana, "cod_cliente": cod_cliente, "records": updated})
    return {"insertados": insertados, "reemplazados": reemplazados}


# ─── CRUD genérico ────────────────────────────────────────────────────────────

def upsert_doc(collection: str, doc_id: str, data: Dict):
    db = get_db()
    db.collection(collection).document(doc_id).set(data)


def delete_doc(collection: str, doc_id: str):
    db = get_db()
    db.collection(collection).document(doc_id).delete()


def delete_docs_batch(collection: str, doc_ids: List[str]):
    db = get_db()
    for doc_id in doc_ids:
        db.collection(collection).document(doc_id).delete()


def get_doc(collection: str, doc_id: str) -> Optional[Dict]:
    db = get_db()
    d = db.collection(collection).document(doc_id).get()
    return {"_id": d.id, **d.to_dict()} if d.exists else None


# ─── Config global ────────────────────────────────────────────────────────────

def load_config() -> Dict:
    """Carga configuración global. Devuelve defaults si no existe."""
    doc = get_doc("config", "global")
    if doc:
        return doc
    return {"semanas_objetivo": 8}


def save_config(data: Dict):
    upsert_doc("config", "global", data)


# ─── Maestros automáticos ─────────────────────────────────────────────────────

def ensure_masters(records: List[Dict]):
    """Crea clientes, marcas, tiendas y artículos que no existan."""
    db = get_db()
    batch = db.batch()

    clientes_ref = db.collection("clientes")
    marcas_ref = db.collection("marcas")
    tiendas_ref = db.collection("tiendas")
    articulos_ref = db.collection("articulos")

    # Recolectar únicos
    clientes = {}
    marcas = set()
    tiendas = {}
    articulos = {}

    for r in records:
        cod_c = str(r.get("cod_cliente", "")).strip()
        nom_c = str(r.get("nombre_cliente", "")).strip()
        marca = str(r.get("marca", "")).strip()
        tienda = str(r.get("nombre_tienda", "")).strip()
        cod_a = str(r.get("cod_articulo", "")).strip()
        nom_a = str(r.get("nombre_articulo", "")).strip()

        if cod_c:
            clientes[cod_c] = nom_c
        if marca:
            marcas.add(marca)
        if tienda:
            tiendas[tienda] = {"nombre": tienda, "cod_cliente": cod_c, "nombre_cliente": nom_c}
        if cod_a:
            articulos[cod_a] = {"nombre_articulo": nom_a, "marca": marca}

    # Escritura en batch (Firestore batch = max 500 ops)
    for cod, nom in clientes.items():
        ref = clientes_ref.document(cod)
        batch.set(ref, {"cod_cliente": cod, "nombre_cliente": nom}, merge=True)

    for marca in marcas:
        ref = marcas_ref.document(marca)
        batch.set(ref, {"nombre": marca}, merge=True)

    for tienda, data in tiendas.items():
        ref = tiendas_ref.document(tienda)
        batch.set(ref, data, merge=True)

    for cod, data in articulos.items():
        ref = articulos_ref.document(cod)
        batch.set(ref, {"cod_articulo": cod, **data}, merge=True)

    batch.commit()


def invalidate_cache():
    """Limpia todos los caches de datos para forzar recarga desde Firestore."""
    load_edi_flat.clear()
    load_collection.clear()
