"""components/charts.py — Gráficos Plotly reutilizables (tema oscuro)."""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional

# Paleta coherente con el tema
COLORS = {
    "primary": "#4f8ef7",
    "success": "#00c48c",
    "warning": "#ffb300",
    "danger": "#ff5252",
    "purple": "#9c27b0",
    "text": "#e8eaed",
    "grid": "#1f2937",
    "bg": "rgba(0,0,0,0)",
    "card_bg": "#161b27",
}

PALETTE = [
    "#4f8ef7", "#00c48c", "#ffb300", "#ff5252", "#9c27b0",
    "#06b6d4", "#f97316", "#a3e635", "#e879f9", "#38bdf8",
]

_LAYOUT_BASE = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["bg"],
    font=dict(family="Inter, sans-serif", color=COLORS["text"], size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(
        bgcolor="rgba(0,0,0,0)", bordercolor=COLORS["grid"],
        borderwidth=1, font=dict(size=11),
    ),
    xaxis=dict(
        gridcolor=COLORS["grid"], linecolor=COLORS["grid"],
        tickfont=dict(size=11),
    ),
    yaxis=dict(
        gridcolor=COLORS["grid"], linecolor=COLORS["grid"],
        tickfont=dict(size=11),
    ),
)


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convierte #RRGGBB a rgba(r,g,b,a).
    Plotly NO acepta hex de 8 dígitos (#RRGGBBAA), usar siempre esta función.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def bar_horizontal(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str = "",
    color: str = COLORS["primary"],
    fmt_x: str = ",.0f",
    height: int = 400,
):
    """Gráfico de barras horizontales para rankings."""
    df = df.sort_values(x_col, ascending=True).tail(15)

    # Color sólido rgba — evita el bug de colorscale con hex+alpha
    bar_color = _hex_to_rgba(color, 0.85)

    fig = go.Figure(
        go.Bar(
            x=df[x_col],
            y=df[y_col],
            orientation="h",
            marker=dict(color=bar_color, line=dict(width=0)),
            text=df[x_col].apply(lambda v: f"{v:,.0f}"),
            textposition="outside",
            textfont=dict(size=11, color=COLORS["text"]),
            hovertemplate=f"<b>%{{y}}</b><br>{x_col}: %{{x:{fmt_x}}}<extra></extra>",
        )
    )
    layout = {**_LAYOUT_BASE, "height": height, "title": dict(
        text=title, font=dict(size=14, color=COLORS["text"]), x=0, pad=dict(l=0)
    )}
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=False)
    return fig


def bar_grouped(
    df: pd.DataFrame,
    x_col: str,
    y_cols: list,
    labels: Optional[list] = None,
    title: str = "",
    height: int = 380,
):
    """Barras agrupadas para comparar métricas."""
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Bar(
            name=labels[i] if labels else col,
            x=df[x_col],
            y=df[col],
            marker_color=PALETTE[i % len(PALETTE)],
            hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:,.0f}}<extra></extra>",
        ))
    layout = {**_LAYOUT_BASE, "height": height, "barmode": "group",
              "title": dict(text=title, font=dict(size=14, color=COLORS["text"]), x=0)}
    fig.update_layout(**layout)
    return fig


def line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_cols: list,
    labels: Optional[list] = None,
    title: str = "",
    height: int = 360,
):
    """Gráfico de líneas para tendencias temporales."""
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Scatter(
            name=labels[i] if labels else col,
            x=df[x_col],
            y=df[col],
            mode="lines+markers",
            line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
            marker=dict(size=5),
            hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:,.1f}}<extra></extra>",
        ))
    layout = {**_LAYOUT_BASE, "height": height,
              "title": dict(text=title, font=dict(size=14, color=COLORS["text"]), x=0)}
    fig.update_layout(**layout)
    return fig


def donut_chart(
    labels: list,
    values: list,
    title: str = "",
    height: int = 320,
):
    """Donut para distribuciones porcentuales."""
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=PALETTE[:len(labels)], line=dict(color="#0e1117", width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, color=COLORS["text"]),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>",
    ))
    layout = {**_LAYOUT_BASE, "height": height,
              "title": dict(text=title, font=dict(size=14, color=COLORS["text"]), x=0.5)}
    fig.update_layout(**layout)
    return fig


def scatter_stock_ema(
    kpis_df: pd.DataFrame,
    semanas_objetivo: int = 8,
    height: int = 420,
):
    """Scatter stock actual vs EMA, coloreado por alerta."""
    if kpis_df.empty:
        return go.Figure()

    color_map = {
        "OK": COLORS["success"],
        "Riesgo": COLORS["warning"],
        "Falta": COLORS["danger"],
        "Sobrestock": COLORS["purple"],
        "Sin rotación": "#6b7280",
    }

    fig = px.scatter(
        kpis_df,
        x="ema",
        y="stock_actual",
        color="alerta",
        color_discrete_map=color_map,
        hover_name="nombre_articulo",
        hover_data={"ema": ":.1f", "stock_actual": ":.0f", "semanas_stock": ":.1f"},
        labels={"ema": "Promedio EMA (ud/sem)", "stock_actual": "Stock actual (ud)"},
        title="Stock actual vs Promedio EMA",
        height=height,
    )
    # Línea de objetivo
    if not kpis_df.empty and kpis_df["ema"].max() > 0:
        x_max = kpis_df["ema"].max() * 1.1
        fig.add_shape(
            type="line",
            x0=0, x1=x_max,
            y0=0, y1=x_max * semanas_objetivo,
            line=dict(color=COLORS["warning"], width=1.5, dash="dash"),
        )
        fig.add_annotation(
            x=x_max * 0.9,
            y=x_max * semanas_objetivo * 1.05,
            text=f"Objetivo: {semanas_objetivo} sem",
            showarrow=False,
            font=dict(color=COLORS["warning"], size=11),
        )

    layout = {**_LAYOUT_BASE, "height": height}
    fig.update_layout(**layout)
    return fig


def coverage_gauge(pct: float, title: str = "Cobertura", height: int = 260):
    """Gauge circular de cobertura."""
    color = (
        COLORS["success"] if pct >= 80
        else COLORS["warning"] if pct >= 50
        else COLORS["danger"]
    )
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 28, "color": color}},
        title={"text": title, "font": {"size": 13, "color": COLORS["text"]}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": COLORS["grid"],
                     "tickfont": {"size": 10}},
            "bar": {"color": color, "thickness": 0.22},
            "bgcolor": COLORS["card_bg"],
            "bordercolor": COLORS["grid"],
            "steps": [
                {"range": [0, 50], "color": COLORS["danger"] + "25"},
                {"range": [50, 80], "color": COLORS["warning"] + "25"},
                {"range": [80, 100], "color": COLORS["success"] + "25"},
            ],
        },
    ))
    layout = {**_LAYOUT_BASE, "height": height, "margin": dict(l=20, r=20, t=50, b=10)}
    fig.update_layout(**layout)
    return fig
