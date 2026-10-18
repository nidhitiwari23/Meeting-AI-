"""Plotly helpers: transparent, dark-theme charts with a consistent palette."""
from __future__ import annotations

import plotly.graph_objects as go

STATUS_COLORS = {"Pending": "#FBBF24", "In Progress": "#60A5FA", "Completed": "#34D399"}
VIOLET = "#8B5CF6"
GRID = "rgba(140,150,255,.12)"
INK = "#C9D0F5"


def style(fig: go.Figure, height: int = 280) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK, size=12),
        legend=dict(orientation="h", y=1.14, x=0.5, xanchor="center", font=dict(color=INK)),
        hoverlabel=dict(bgcolor="#121a45", font_color="#fff", bordercolor="#6c5ce7"),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color="#8E99CC"))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color="#8E99CC"))
    return fig


def donut(labels: list[str], values: list[int], colors: list[str], center: str) -> go.Figure:
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.7, marker=dict(colors=colors, line=dict(color="#0A1030", width=3)),
                           textinfo="none", sort=False, hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
    fig.add_annotation(text=center, x=0.5, y=0.5, showarrow=False, font=dict(size=26, color="#fff", family="Sora"))
    style(fig, 270)
    fig.update_layout(legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"), margin=dict(l=8, r=8, t=8, b=36))
    return fig


def hbar(labels: list[str], values: list[int], color: str = VIOLET) -> go.Figure:
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker=dict(color=color, line=dict(width=0)),
                           hovertemplate="%{y}: %{x} open task(s)<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(bargap=0.45)
    return style(fig, max(180, 46 * len(labels) + 40))


def vbar(labels: list[str], values: list[int], color: str = "#3B82F6") -> go.Figure:
    fig = go.Figure(go.Bar(x=labels, y=values, marker=dict(color=color), hovertemplate="%{x}: %{y} task(s) due<extra></extra>"))
    fig.update_layout(bargap=0.5)
    return style(fig, 240)
