"""components/kpi_cards.py — Tarjetas KPI reutilizables."""
import streamlit as st
from typing import Optional


def kpi_card(
    label: str,
    value: str,
    icon: str = "📊",
    delta: Optional[str] = None,
    delta_positive: Optional[bool] = None,
    color: str = "#4f8ef7",
    suffix: str = "",
):
    """Renderiza una tarjeta KPI con gradiente y delta opcional."""
    delta_html = ""
    if delta is not None:
        if delta_positive is True:
            delta_color = "#00c48c"
            arrow = "▲"
        elif delta_positive is False:
            delta_color = "#ff5252"
            arrow = "▼"
        else:
            delta_color = "#9ca3af"
            arrow = "●"
        delta_html = (
            f"<div style='font-size:0.8rem;color:{delta_color};"
            f"font-weight:600;margin-top:4px;'>{arrow} {delta}</div>"
        )

    st.markdown(
        f"""
        <div style="
            background:linear-gradient(135deg,#161b27 0%,#1a2035 100%);
            border:1px solid #2a3148;border-radius:16px;
            padding:22px 20px 18px;position:relative;overflow:hidden;
            box-shadow:0 4px 24px rgba(0,0,0,0.3);
        ">
            <div style="
                position:absolute;top:-20px;right:-20px;
                width:80px;height:80px;border-radius:50%;
                background:{color};opacity:0.08;
            "></div>
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                <span style="font-size:1.6rem;">{icon}</span>
                <span style="font-size:0.75rem;color:#6b7280;font-weight:600;
                             text-transform:uppercase;letter-spacing:0.06em;">{label}</span>
            </div>
            <div style="
                font-size:1.9rem;font-weight:800;color:{color};
                letter-spacing:-0.03em;line-height:1.1;
            ">{value}{suffix}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_badge(label: str, color: str):
    """Pill con color de alerta."""
    bg = color + "22"
    st.markdown(
        f"<span style='display:inline-block;padding:3px 12px;border-radius:20px;"
        f"background:{bg};color:{color};font-size:0.78rem;font-weight:700;"
        f"border:1px solid {color}44;'>{label}</span>",
        unsafe_allow_html=True,
    )


def semanas_stock_badge(value, semanas_objetivo: int = 8):
    """Renderiza el valor de semanas de stock con color de alerta inline."""
    if value is None or (hasattr(value, "__class__") and value != value):  # NaN check
        label, color = "Sin rotación", "#6b7280"
    else:
        dif = float(value) - semanas_objetivo
        if abs(dif) <= 1:
            label, color = f"{value:.1f} sem", "#00c48c"
        elif abs(dif) <= 3:
            label, color = f"{value:.1f} sem ⚠️", "#ffb300"
        elif dif <= -4:
            label, color = f"{value:.1f} sem 🔴", "#ff5252"
        else:
            label, color = f"{value:.1f} sem 🟣", "#9c27b0"

    bg = color + "22"
    return (
        f"<span style='padding:2px 10px;border-radius:12px;"
        f"background:{bg};color:{color};font-size:0.8rem;"
        f"font-weight:700;border:1px solid {color}44;'>{label}</span>"
    )


def section_header(title: str, icon: str = ""):
    """Cabecera de sección con separador."""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;
                    margin:24px 0 16px;padding-bottom:10px;
                    border-bottom:1px solid #1f2937;">
            <span style="font-size:1.2rem;">{icon}</span>
            <span style="font-size:1.05rem;font-weight:700;color:#e5e7eb;">{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(message: str = "No hay datos para mostrar con los filtros actuales."):
    st.markdown(
        f"""
        <div style="text-align:center;padding:60px 20px;color:#4b5563;">
            <div style="font-size:3rem;margin-bottom:12px;">📭</div>
            <div style="font-size:1rem;font-weight:500;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
