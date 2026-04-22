"""core/auth.py — Autenticación de sesión única."""
import streamlit as st


def check_auth() -> bool:
    """Retorna True si el usuario ya está autenticado en session_state."""
    return st.session_state.get("authenticated", False)


def login_form():
    """Renderiza el formulario de login y gestiona la autenticación."""
    st.markdown(
        """
        <style>
        .login-wrap {
            max-width: 420px;
            margin: 4vh auto 0 auto;
            padding: 26px 28px 18px 28px;
            background: linear-gradient(135deg,#161b27 0%,#1a2035 100%);
            border: 1px solid #2a3148;
            border-radius: 20px;
        }
        .login-wrap h2, .login-wrap p {
            text-align: center;
            margin: 0;
        }
        .login-wrap .logo {
            text-align: center;
            font-size: 2.2rem;
            margin-bottom: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("""
    <div class="login-wrap">
        <div class="logo">📊</div>
        <h2 style="color:#e8eaed;font-weight:800;">Stock Grandes Marcas</h2>
        <p style="color:#6b7280;font-size:0.85rem;margin-top:4px;margin-bottom:16px;">Analytics Dashboard · v2.0</p>
    </div>
    """, unsafe_allow_html=True)

    # Centro el formulario con columnas (pegado a la tarjeta superior)
    col1, col2, col3 = st.columns([1.2, 2, 1.2])
    with col2:
        with st.form("login_form", clear_on_submit=False):
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
