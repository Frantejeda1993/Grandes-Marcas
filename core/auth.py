"""core/auth.py — Autenticación de sesión única."""
import streamlit as st


def check_auth() -> bool:
    """Retorna True si el usuario ya está autenticado en session_state."""
    return st.session_state.get("authenticated", False)


def login_form():
    """Renderiza el formulario de login y gestiona la autenticación."""
    st.markdown("""
    <div style="display:flex;justify-content:center;align-items:center;min-height:80vh;">
    <div style="
        max-width:420px;width:100%;
        background:linear-gradient(135deg,#161b27 0%,#1a2035 100%);
        border:1px solid #2a3148;border-radius:20px;
        padding:48px 40px;text-align:center;
    ">
        <div style="font-size:3rem;margin-bottom:8px;">📊</div>
        <h2 style="color:#e8eaed;font-weight:800;margin:0 0 4px;">Stock Grandes Marcas</h2>
        <p style="color:#6b7280;font-size:0.85rem;margin-bottom:32px;">Analytics Dashboard · v2.0</p>
    </div>
    </div>
    """, unsafe_allow_html=True)

    # Centro el formulario con columnas
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            st.markdown(
                "<h3 style='text-align:center;color:#e8eaed;margin-bottom:20px;'>Iniciar sesión</h3>",
                unsafe_allow_html=True,
            )
            usuario = st.text_input("Usuario", placeholder="Athena")
            contrasena = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", width="stretch", type="primary")

        if submitted:
            try:
                expected_user = st.secrets["auth"]["username"]
                expected_pass = st.secrets["auth"]["password"]
            except Exception:
                # Fallback para desarrollo local sin secrets.toml completo
                expected_user = "Athena"
                expected_pass = "Athena2026*"

            if usuario == expected_user and contrasena == expected_pass:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos.")
