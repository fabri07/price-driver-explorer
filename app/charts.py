"""
Gráficos plotly para la interfaz.
==================================

El gráfico principal es un diagrama de barras de los pesos de las variables:
- ordenado por |peso| (las más asociadas arriba),
- color por signo (verde = mismo sentido, rojo = sentido opuesto),
- una barra de error que representa la incertidumbre (1 - estabilidad): cuanto más
  larga, menos confiable es el peso.
"""

from __future__ import annotations

import textwrap

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.fred_series import glosa_por_nombre
from config.relationship_graph import descripcion_ticker
from modeling.results import AssetResult, VariableWeight

# ---------------------------------------------------------------------
# Paleta tipo terminal financiera (combina con .streamlit/config.toml).
# ---------------------------------------------------------------------
_BG = "#0A0F0C"          # negro con leve tinte verde
_TXT = "#E4EDE8"         # papel frío (blanco levemente verde)
_GRID = "rgba(0,217,130,0.08)"   # grilla verde muy tenue
_VERDE = "#00D982"       # acento / alza / mismo sentido (verde fósforo)
_ACENTO = _VERDE         # acento de la identidad (líneas, precio)
_ROJO = "#E5484D"        # baja / sentido opuesto (convención financiera)

_FONT_TITULO = "Playfair Display, Georgia, serif"   # serif editorial (titulares)
_FONT_DATOS = "IBM Plex Mono, SFMono-Regular, monospace"  # datos (terminal)

# Colores por signo (alineados a la paleta terminal).
_COLOR_POS = _VERDE  # mismo sentido
_COLOR_NEG = _ROJO   # sentido opuesto


def _aplicar_tema(fig: go.Figure, titulo: str | None = None) -> go.Figure:
    """Aplica el look 'terminal verde' a una figura plotly.

    El título se ancla ARRIBA-IZQUIERDA y se reserva margen superior (t=72) para que ni
    la barra de herramientas de plotly (arriba-derecha) ni el selector de rango lo tapen.
    """
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(family=_FONT_DATOS, color=_TXT, size=12),
        title=dict(
            font=dict(family=_FONT_TITULO, size=19, color=_TXT),
            x=0, xanchor="left", y=0.97, yanchor="top",
        ),
        margin=dict(l=10, r=10, t=72, b=10),
    )
    fig.update_xaxes(gridcolor=_GRID, zerolinecolor=_GRID, linecolor=_GRID)
    fig.update_yaxes(gridcolor=_GRID, zerolinecolor=_GRID, linecolor=_GRID)
    if titulo:
        fig.update_layout(title_text=titulo)
    return fig


def _wrap(texto: str, ancho: int = 60) -> str:
    """Parte un texto largo en varias líneas para que el tooltip no sea gigante."""
    return "<br>".join(textwrap.wrap(texto, width=ancho)) if texto else ""


def _que_es(v: VariableWeight) -> str:
    """Descripción legible de la variable (macro: glosa; activo: ficha del ticker)."""
    glosa = glosa_por_nombre(v.variable)
    if glosa:
        return glosa
    # Variable de activo: el nombre es "TICKER (rol)"; extraemos el ticker.
    ticker = v.variable.split(" (")[0].strip()
    desc = descripcion_ticker(ticker)
    if desc:
        return desc
    # Fallback: metadata de origen del dataset.
    return v.descripcion or "Variable de contexto."


def _etiqueta_estabilidad(estab: float) -> str:
    if estab >= 0.66:
        return f"alta ({estab:.2f})"
    if estab >= 0.33:
        return f"media ({estab:.2f})"
    return f"baja ({estab:.2f})"


def _etiqueta_magnitud(peso_abs: float, peso_max: float) -> str:
    """Magnitud relativa al mayor peso mostrado (comparable dentro del mismo método)."""
    if peso_max <= 0:
        return "—"
    ratio = peso_abs / peso_max
    if ratio >= 0.5:
        return "fuerte"
    if ratio >= 0.15:
        return "moderada"
    return "débil"


def _hover_variable(v: VariableWeight, ticker: str, peso_max: float) -> str:
    """Tooltip educativo: qué es la variable + su asociación con el activo."""
    mismo = v.signo == "+"
    sentido = (
        f"📈 Asociación POSITIVA: tendió a moverse en el MISMO sentido que {ticker}."
        if mismo else
        f"📉 Asociación NEGATIVA: tendió a moverse en sentido OPUESTO a {ticker}."
    )
    magnitud = _etiqueta_magnitud(abs(v.peso), peso_max)
    estab = _etiqueta_estabilidad(v.estabilidad)
    return (
        f"<b>{v.variable}</b><br>"
        f"<i>Qué es:</i><br>{_wrap(_que_es(v))}<br><br>"
        f"<i>Impacto en {ticker}:</i><br>{_wrap(sentido)}<br>"
        f"Magnitud: <b>{magnitud}</b> (peso {v.peso:.4f}) · Estabilidad: <b>{estab}</b><br>"
        f"<i>Asociación histórica, no causa ni predicción.</i>"
    )


def weights_bar_chart(result: AssetResult, metodo: str = "lasso", top_n: int = 15) -> go.Figure:
    """Barras horizontales de los pesos de un método, con incertidumbre.

    Parameters
    ----------
    result : AssetResult.
    metodo : "lasso" | "xgboost_shap" — qué método mostrar.
    top_n : cuántas variables (las de mayor |peso|).
    """
    variables = [v for v in result.variables if v.metodo == metodo]
    variables = sorted(variables, key=lambda v: abs(v.peso), reverse=True)[:top_n]
    variables = list(reversed(variables))  # plotly dibuja de abajo hacia arriba

    if not variables:
        fig = go.Figure()
        fig.add_annotation(
            text=f"Sin variables para el método '{metodo}'.",
            showarrow=False,
            font=dict(size=14),
        )
        return fig

    nombres = [v.variable for v in variables]
    # Peso con signo (para que la barra apunte a izquierda/derecha según el sentido).
    pesos_signados = [v.peso if v.signo == "+" else -v.peso for v in variables]
    colores = [_COLOR_POS if v.signo == "+" else _COLOR_NEG for v in variables]
    # Incertidumbre = 1 - estabilidad, escalada al tamaño del peso (banda de error).
    errores = [abs(p) * (1.0 - v.estabilidad) for p, v in zip(pesos_signados, variables)]

    peso_max = max((abs(v.peso) for v in variables), default=0.0)
    textos_hover = [_hover_variable(v, result.ticker, peso_max) for v in variables]
    # Valor del peso (con signo) DENTRO de cada barra, en monospace de datos.
    etiquetas = [f"{p:+.3f}" for p in pesos_signados]

    fig = go.Figure(
        go.Bar(
            x=pesos_signados,
            y=nombres,
            orientation="h",
            marker_color=colores,
            text=etiquetas,
            texttemplate="%{text}",
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(family=_FONT_DATOS, size=11, color=_BG),
            constraintext="none",
            cliponaxis=False,
            error_x=dict(type="data", array=errores, color="rgba(228,237,232,0.45)", thickness=1.5),
            hovertext=textos_hover,
            hoverinfo="text",
            hoverlabel=dict(align="left", bgcolor="rgba(10,15,12,0.96)",
                            bordercolor=_VERDE,
                            font=dict(size=12, color=_TXT)),
        )
    )
    _aplicar_tema(fig, titulo=f"Variables asociadas a {result.ticker} · método: {metodo}")
    fig.update_layout(
        xaxis_title="Peso (← sentido opuesto | mismo sentido →)",
        yaxis_title="",
        height=max(300, 28 * len(variables) + 80),
    )
    fig.add_vline(x=0, line_width=1, line_color="rgba(230,225,214,0.35)")
    return fig


# Selector de rango anclado ARRIBA-DERECHA (el título va arriba-izquierda → no se tapan).
_BOTONES_RANGO = dict(
    buttons=[
        dict(count=1, label="1M", step="month", stepmode="backward"),
        dict(count=6, label="6M", step="month", stepmode="backward"),
        dict(count=1, label="YTD", step="year", stepmode="todate"),
        dict(count=1, label="1A", step="year", stepmode="backward"),
        dict(step="all", label="TODO"),
    ],
    bgcolor="#111815",
    bordercolor="rgba(0,217,130,0.30)",
    borderwidth=1,
    activecolor=_VERDE,
    font=dict(color=_TXT, family=_FONT_DATOS, size=11),
    x=1, xanchor="right", y=1.10, yanchor="top",
)


def price_candlestick_chart(
    ohlc: pd.DataFrame,
    ticker: str,
    max_52s: float | None = None,
    min_52s: float | None = None,
) -> go.Figure:
    """Gráfico de velas (candlestick) con volumen, estilo terminal financiera.

    `ohlc` debe tener columnas 'open','high','low','close' (y opcionalmente 'volume'),
    indexadas por fecha. Si faltan columnas OHLC, cae a una línea de cierre.
    """
    cols = {c.lower() for c in ohlc.columns}
    tiene_ohlc = {"open", "high", "low", "close"}.issubset(cols)

    # Fallback: si no hay OHLC completo, línea de cierre con el mismo tema.
    if not tiene_ohlc:
        serie = ohlc["close"] if "close" in ohlc.columns else ohlc.iloc[:, 0]
        fig = go.Figure(
            go.Scatter(x=serie.index, y=serie.values, mode="lines", name="Cierre",
                       line=dict(color=_ACENTO, width=1.4))
        )
        _aplicar_tema(fig, titulo=f"{ticker} — precio")
        fig.update_layout(height=360, yaxis_title="Precio (US$)")
        return fig

    tiene_vol = "volume" in cols
    fig = make_subplots(
        rows=2 if tiene_vol else 1, cols=1, shared_xaxes=True,
        row_heights=[0.78, 0.22] if tiene_vol else [1.0],
        vertical_spacing=0.03,
    )

    fig.add_trace(
        go.Candlestick(
            x=ohlc.index,
            open=ohlc["open"], high=ohlc["high"],
            low=ohlc["low"], close=ohlc["close"],
            name=ticker,
            increasing=dict(line=dict(color=_VERDE), fillcolor=_VERDE),
            decreasing=dict(line=dict(color=_ROJO), fillcolor=_ROJO),
        ),
        row=1, col=1,
    )

    if tiene_vol:
        colores_vol = [
            _VERDE if c >= o else _ROJO
            for o, c in zip(ohlc["open"], ohlc["close"])
        ]
        fig.add_trace(
            go.Bar(x=ohlc.index, y=ohlc["volume"], name="Volumen",
                   marker_color=colores_vol, marker_line_width=0, opacity=0.55),
            row=2, col=1,
        )
        fig.update_yaxes(title_text="Vol.", row=2, col=1, showgrid=False)

    # Bandas de máximo/mínimo de 52 semanas (referencia).
    if max_52s:
        fig.add_hline(y=max_52s, line_dash="dot", line_color=_VERDE,
                      annotation_text="máx 52s", annotation_position="top left", row=1, col=1)
    if min_52s:
        fig.add_hline(y=min_52s, line_dash="dot", line_color=_ROJO,
                      annotation_text="mín 52s", annotation_position="bottom left", row=1, col=1)

    _aplicar_tema(fig, titulo=f"{ticker} — velas diarias")
    fig.update_layout(
        height=460,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    # Selector de rango (1M/6M/YTD/1A/TODO) sobre el eje x principal.
    eje_x = "xaxis" if not tiene_vol else "xaxis2"
    fig.update_layout(**{eje_x: dict(rangeselector=_BOTONES_RANGO)})
    fig.update_yaxes(title_text="Precio (US$)", row=1, col=1)
    return fig


# Compatibilidad: el Overview puede llamar a price_line_chart con una Serie de cierre.
def price_line_chart(close: pd.Series, ticker: str, max_52s: float | None = None,
                     min_52s: float | None = None) -> go.Figure:
    """Línea de cierre (fallback cuando no hay OHLC)."""
    df = pd.DataFrame({"close": close})
    return price_candlestick_chart(df, ticker, max_52s, min_52s)
