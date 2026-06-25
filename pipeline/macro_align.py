"""
Alineación anti look-ahead de series macro al calendario diario.
================================================================

★ DEFENSA CONTRA LOOK-AHEAD BIAS ★

Problema: una serie macro de baja frecuencia (CPI mensual, GDP trimestral) viene
fechada por su PERÍODO DE REFERENCIA, pero recién se publica semanas después. Si la
forward-filleáramos desde su fecha de referencia, un modelo "sabría" el CPI de marzo
desde el 1 de marzo — información que en la práctica no existía hasta mediados de abril.

Solución:
1. Desplazamos cada observación hacia adelante `publication_lag_days` días → su fecha
   real (conservadora) de disponibilidad.
2. Reindexamos al calendario diario de mercado.
3. Forward-fill SOLO a partir de esa fecha de disponibilidad.

Así, en cada día t, el valor macro usado es el más reciente que YA se había publicado
en t. Nunca un valor del futuro.
"""

from __future__ import annotations

import pandas as pd

# Observaciones por año según la frecuencia nativa de la serie. Se usa para calcular
# la variación interanual (YoY) sobre la frecuencia ORIGINAL, antes de pasar a diario.
_PERIODOS_POR_ANIO: dict[str, int] = {
    "diaria": 252,     # días de mercado
    "semanal": 52,
    "mensual": 12,
    "trimestral": 4,
}


def aplicar_transformacion(serie: pd.Series, transformacion: str, freq: str) -> pd.Series:
    """Convierte una serie de NIVEL a una forma estacionaria, en frecuencia nativa.

    ★ POR QUÉ ★
    Muchas series macro son *niveles con tendencia* (CPI, PBI, nóminas, producción,
    precios de commodities): crecen de forma sostenida en el tiempo. Como el precio de
    un activo también suele subir, una regresión cruda puede encontrar correlaciones
    ESPURIAS por co-tendencia (ambos suben juntos sin relación real). La defensa
    estándar en econometría es transformar el nivel en una *tasa de cambio*, que es
    aproximadamente estacionaria.

    Transformaciones soportadas
    ----------------------------
    - "nivel" : se deja tal cual. Apropiado para series ya estacionarias (tasas de
      interés, spreads, VIX, índices de sentimiento acotados, tasa de desempleo).
    - "yoy"   : variación interanual (%) = valor / valor_hace_1_año − 1. Quita la
      tendencia de largo plazo. Es como se reporta la inflación. Para precios, índices
      y niveles que crecen con la economía.
    - "mom"   : variación período-a-período (%) sobre la frecuencia nativa (mes contra
      mes, semana contra semana). Más ruidosa pero más reactiva.

    La transformación se hace ANTES de desplazar por el lag y forward-fillear a diario,
    para que la ventana (ej. 12 meses) cuente períodos reales de la serie, no días
    repetidos por el ffill.
    """
    if transformacion == "nivel" or serie.empty:
        return serie

    s = serie.sort_index()
    if transformacion == "yoy":
        periodos = _PERIODOS_POR_ANIO.get(freq, 12)
        out = s.pct_change(periods=periodos)
    elif transformacion == "mom":
        out = s.pct_change(periods=1)
    else:
        raise ValueError(
            f"transformación '{transformacion}' desconocida "
            f"(usá 'nivel', 'yoy' o 'mom')."
        )
    out.name = serie.name
    return out.dropna()


def align_macro_no_lookahead(
    serie: pd.Series,
    publication_lag_days: int,
    market_calendar: pd.DatetimeIndex,
    *,
    transformacion: str = "nivel",
    freq: str = "diaria",
) -> pd.Series:
    """Alinea una serie macro al calendario de mercado sin look-ahead.

    Parameters
    ----------
    serie : Series macro en frecuencia nativa, fechada por período de referencia.
    publication_lag_days : retraso conservador entre referencia y publicación.
    market_calendar : DatetimeIndex de los días de mercado (índice del target).
    transformacion : "nivel" | "yoy" | "mom" — cómo volver la serie estacionaria
        antes de alinearla (ver `aplicar_transformacion`).
    freq : frecuencia nativa de la serie (para calcular la ventana YoY correcta).

    Returns
    -------
    Series reindexada a `market_calendar`, forward-filleada solo desde la fecha de
    disponibilidad real. Días previos a la primera publicación quedan NaN.
    """
    if serie.empty:
        return pd.Series(index=market_calendar, dtype=float, name=serie.name)

    # 0) Volver la serie estacionaria (si corresponde) en su frecuencia nativa.
    serie = aplicar_transformacion(serie, transformacion, freq)
    if serie.empty:
        return pd.Series(index=market_calendar, dtype=float, name=serie.name)

    s = serie.sort_index().copy()

    # 1) Desplazar el índice a la fecha de disponibilidad real.
    s.index = s.index + pd.Timedelta(days=publication_lag_days)

    # 2) Unir el índice macro (ya desplazado) con el calendario de mercado, ordenar,
    #    forward-fill, y quedarnos solo con los días de mercado.
    union_idx = s.index.union(market_calendar).sort_values()
    s_aligned = s.reindex(union_idx).ffill()
    s_aligned = s_aligned.reindex(market_calendar)

    s_aligned.name = serie.name
    return s_aligned


def first_available_date(serie: pd.Series, publication_lag_days: int) -> pd.Timestamp | None:
    """Primera fecha en que la serie estuvo disponible (para tests anti look-ahead)."""
    if serie.empty:
        return None
    return serie.sort_index().index[0] + pd.Timedelta(days=publication_lag_days)
