"""app.py — Entry point de Stock Grandes Marcas V2.0.

Streamlit Cloud: ejecutar con `streamlit run app.py`
"""
import streamlit as st

# ─── Configuración de página (DEBE ser lo primero) ───────────────────────────
st.set_page_config(
    page_title="Stock Grandes Marcas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS Global ───────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
}

/* ── Fondo principal ── */
.stApp { background-color: #0e1117; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #111827 100%) !important;
    border-right: 1px solid #1f2937 !important;
}
section[data-testid="stSidebar"] .stButton button {
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    transition: all 0.18s ease !important;
}

/* ── Tipografía general ── */
h1, h2, h3, h4 { color: #e8eaed !important; letter-spacing: -0.02em; }
p, span, div { color: #c9d1d9; }

/* ── Expanders ── */
details[data-testid="stExpander"] summary {
    background: linear-gradient(90deg, #161b27, #1a2035) !important;
    border: 1px solid #2a3148 !important;
    border-radius: 10px !important;
    padding: 10px 16px !important;
    font-weight: 600 !important;
    color: #e8eaed !important;
    transition: background 0.2s;
}
details[data-testid="stExpander"] summary:hover {
    background: linear-gradient(90deg, #1a2035, #1e2845) !important;
}
details[data-testid="stExpander"] > div {
    border: 1px solid #2a3148 !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    background: #111827 !important;
    padding: 16px !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #1f2937 !important;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px 8px 0 0 !important;
    color: #6b7280 !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 8px 16px !important;
    transition: all 0.2s;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #161b27, #1a2035) !important;
    color: #4f8ef7 !important;
    border-bottom: 2px solid #4f8ef7 !important;
}

/* ── Dataframe / tablas ── */
.stDataFrame { border-radius: 12px !important; overflow: hidden !important; }
.stDataFrame iframe { border-radius: 12px !important; }

/* ── Inputs ── */
.stTextInput input, .stNumberInput input, .stSelectbox select {
    background: #161b27 !important;
    border: 1px solid #2a3148 !important;
    border-radius: 8px !important;
    color: #e8eaed !important;
}

/* ── Multiselect ── */
.stMultiSelect [data-baseweb="select"] > div {
    background: #161b27 !important;
    border: 1px solid #2a3148 !important;
    border-radius: 8px !important;
}

/* ── Botones ── */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #4f8ef7, #3b7de8) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 12px rgba(79,142,247,0.3) !important;
    transition: all 0.2s ease !important;
}
.stButton button[kind="primary"]:hover {
    box-shadow: 0 4px 20px rgba(79,142,247,0.5) !important;
    transform: translateY(-1px) !important;
}
.stButton button[kind="secondary"] {
    background: #161b27 !important;
    border: 1px solid #2a3148 !important;
    color: #9ca3af !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
.stButton button[kind="secondary"]:hover {
    border-color: #4f8ef7 !important;
    color: #4f8ef7 !important;
}

/* ── Progress bar ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #4f8ef7, #9c27b0) !important;
    border-radius: 4px !important;
}

/* ── Métricas ── */
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 800 !important;
    color: #4f8ef7 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    color: #6b7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

/* ── Dividers ── */
hr { border-color: #1f2937 !important; margin: 12px 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0e1117; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4b5563; }

/* ── Ocultar menú hamburguesa, footer y nav automático de páginas ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarNavItems"] { display: none !important; }
[data-testid="stSidebarNavSeparator"] { display: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ─── Auth ─────────────────────────────────────────────────────────────────────
from core.auth import check_auth, login_form

if not check_auth():
    login_form()
    st.stop()

# ─── Firebase / Firestore ─────────────────────────────────────────────────────
try:
    from core.firestore import init_db, load_edi_flat, invalidate_cache
    init_db()
except Exception as exc:
    st.error(
        f"❌ **Error al conectar con Firebase.**\n\n"
        f"Comprueba que el archivo `.streamlit/secrets.toml` contiene las credenciales correctas.\n\n"
        f"Detalle: `{exc}`"
    )
    st.stop()

# ─── Session defaults ─────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"
if "filters" not in st.session_state:
    st.session_state["filters"] = {"clientes": [], "marcas": [], "tiendas": [], "articulos": []}
if "semanas_objetivo" not in st.session_state:
    # Cargar desde Firestore si existe
    try:
        from core.firestore import load_config
        cfg = load_config()
        st.session_state["semanas_objetivo"] = cfg.get("semanas_objetivo", 8)
    except Exception:
        st.session_state["semanas_objetivo"] = 8

# ─── Cargar DataFrame maestro ─────────────────────────────────────────────────
try:
    with st.spinner("📡 Sincronizando datos…"):
        df_master = load_edi_flat()
except Exception as exc:
    st.error(
        "❌ **No se pudieron sincronizar los datos de Firestore.**\n\n"
        "Si estás en Streamlit Cloud, valida `firebase.private_key` en "
        "`.streamlit/secrets.toml` (debe conservar saltos de línea reales) y "
        "que la clave del service account siga activa en Google Cloud.\n\n"
        f"Detalle: `{exc}`"
    )
    st.stop()

st.session_state["df_master"] = df_master

# Aplicar filtros globales
from core.kpi import apply_filters
df_filtered = apply_filters(df_master, st.session_state["filters"])
st.session_state["df_filtered"] = df_filtered

# ─── Sidebar ──────────────────────────────────────────────────────────────────
from components.sidebar import render_sidebar
render_sidebar(df=df_master)

# ─── Router ───────────────────────────────────────────────────────────────────
page = st.session_state.get("page", "Dashboard")

if page == "Dashboard":
    from pages.dashboard import main; main()
elif page == "Cliente":
    from pages.cliente import main; main()
elif page == "Categoría":
    from pages.categoria import main; main()
elif page == "Tienda":
    from pages.tienda import main; main()
elif page == "Configuración":
    from pages.configuracion import main; main()
elif page == "BD":
    from pages.bd import main; main()
elif page == "Inputs":
    from pages.inputs_page import main; main()
else:
    from pages.dashboard import main; main()
