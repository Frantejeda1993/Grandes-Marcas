"""components/sidebar.py — Sidebar de navegación + filtros globales."""
import streamlit as st
from core.kpi import get_filter_options


NAV_ITEMS = [
    ("📊", "Dashboard"),
    ("👤", "Cliente"),
    ("🗂️", "Categoría"),
    ("🏪", "Tienda"),
    ("⚙️", "Configuración"),
    ("🗄️", "BD"),
    ("📤", "Inputs"),
]


def _nav_button(icon: str, label: str):
    active = st.session_state.get("page") == label
    btn_style = "primary" if active else "secondary"
    if st.button(
        f"{icon}  {label}",
        key=f"nav_{label}",
        width="stretch",
        type=btn_style,
    ):
        st.session_state["page"] = label
        st.rerun()


def render_sidebar(df=None):
    with st.sidebar:
        # ── Marca ──────────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="text-align:center;padding:20px 0 12px;">
                <div style="font-size:2.4rem;">📊</div>
                <div style="font-size:1.05rem;font-weight:800;color:#e8eaed;
                            letter-spacing:-0.02em;">Stock Grandes Marcas</div>
                <div style="font-size:0.72rem;color:#4f8ef7;font-weight:600;
                            letter-spacing:0.08em;text-transform:uppercase;
                            margin-top:2px;">Analytics · v2.0</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Navegación ─────────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:0.72rem;color:#6b7280;font-weight:600;"
            "text-transform:uppercase;letter-spacing:0.08em;"
            "padding:0 4px 8px;'>Navegación</div>",
            unsafe_allow_html=True,
        )
        for icon, label in NAV_ITEMS:
            _nav_button(icon, label)

        st.divider()

        # ── Filtros globales ────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:0.72rem;color:#6b7280;font-weight:600;"
            "text-transform:uppercase;letter-spacing:0.08em;"
            "padding:0 4px 8px;'>Filtros Globales</div>",
            unsafe_allow_html=True,
        )

        # Obtener opciones del DataFrame maestro (si disponible)
        if df is not None and not df.empty:
            opts = get_filter_options(df)
        else:
            opts = {"clientes": [], "marcas": [], "tiendas": [], "articulos": []}

        filters = st.session_state.get("filters", {
            "clientes": [], "marcas": [], "tiendas": [], "articulos": []
        })

        filters["clientes"] = st.multiselect(
            "🏢 Clientes",
            options=opts.get("clientes", []),
            default=[v for v in filters.get("clientes", []) if v in opts.get("clientes", [])],
            placeholder="Todos los clientes",
            key="flt_clientes",
        )
        filters["marcas"] = st.multiselect(
            "🏷️ Marca",
            options=opts.get("marcas", []),
            default=[v for v in filters.get("marcas", []) if v in opts.get("marcas", [])],
            placeholder="Todas las marcas",
            key="flt_marcas",
        )
        filters["tiendas"] = st.multiselect(
            "🏪 Tienda",
            options=opts.get("tiendas", []),
            default=[v for v in filters.get("tiendas", []) if v in opts.get("tiendas", [])],
            placeholder="Todas las tiendas",
            key="flt_tiendas",
        )
        filters["articulos"] = st.multiselect(
            "📦 Artículo",
            options=opts.get("articulos", []),
            default=[v for v in filters.get("articulos", []) if v in opts.get("articulos", [])],
            placeholder="Todos los artículos",
            key="flt_articulos",
        )

        st.session_state["filters"] = filters

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Limpiar", width="stretch", key="btn_clear_filters"):
                st.session_state["filters"] = {
                    "clientes": [], "marcas": [], "tiendas": [], "articulos": []
                }
                st.rerun()
        with col2:
            n_active = sum(1 for v in filters.values() if v)
            st.markdown(
                f"<div style='text-align:center;padding:6px 0;"
                f"color:{'#4f8ef7' if n_active else '#6b7280'};"
                f"font-size:0.8rem;font-weight:600;'>"
                f"{'🔵 ' + str(n_active) + ' activo' + ('s' if n_active != 1 else '') if n_active else '⚪ Sin filtros'}"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Configuración rápida ───────────────────────────────────────────
        st.markdown(
            "<div style='font-size:0.72rem;color:#6b7280;font-weight:600;"
            "text-transform:uppercase;letter-spacing:0.08em;"
            "padding:0 4px 8px;'>Configuración</div>",
            unsafe_allow_html=True,
        )
        semanas_obj = st.number_input(
            "🎯 Semanas objetivo stock",
            min_value=1,
            max_value=52,
            value=st.session_state.get("semanas_objetivo", 8),
            step=1,
            key="input_semanas_obj",
        )
        st.session_state["semanas_objetivo"] = semanas_obj

        st.divider()

        # ── Logout ─────────────────────────────────────────────────────────
        if st.button("🚪 Cerrar sesión", width="stretch", key="btn_logout"):
            st.session_state.clear()
            st.rerun()
