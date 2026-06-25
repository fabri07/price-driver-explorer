"""
Panel macro: valores actuales de FRED + el peso que el modelo les asignó.
========================================================================

Cruza dos cosas, para el activo elegido:
- el VALOR más reciente de cada serie macro (y su variación), y
- el PESO/SENTIDO/ESTABILIDAD que el modelo estimó para esa serie sobre el activo.

Así el panel responde, en lenguaje de asociación: "la inflación está en X (subió);
históricamente, NVDA tendió a moverse en sentido opuesto cuando la inflación subía,
con estabilidad media". NO es predicción ni recomendación.
"""

from __future__ import annotations

from config.fred_series import FRED_SERIES
from data_sources.base import MacroDataSource
from modeling.results import AssetResult


def extract_macro_weights(result: AssetResult) -> dict[str, dict]:
    """Extrae del AssetResult los pesos de las variables macro, por nombre de serie.

    Prefiere el coeficiente de Lasso (interpretable); si una serie solo aparece en
    XGBoost/SHAP, usa ese. Devuelve {nombre_serie -> {peso, signo, estabilidad, metodo}}.
    """
    nombres_macro = {spec.nombre for spec in FRED_SERIES}
    pesos: dict[str, dict] = {}
    for v in result.variables:
        if v.variable not in nombres_macro:
            continue
        # Lasso tiene prioridad sobre xgboost_shap.
        actual = pesos.get(v.variable)
        if actual is None or (actual["metodo"] != "lasso" and v.metodo == "lasso"):
            pesos[v.variable] = {
                "peso": v.peso,
                "signo": v.signo,
                "estabilidad": v.estabilidad,
                "metodo": v.metodo,
            }
    return pesos


def build_macro_panel(
    macro_weights: dict[str, dict],
    macro_source: MacroDataSource,
    start: str,
    end: str,
) -> list[dict]:
    """Arma las filas del panel macro.

    Parameters
    ----------
    macro_weights : salida de `extract_macro_weights` (peso por nombre de serie).
    macro_source : implementación de MacroDataSource (inyectada).
    start, end : ventana de fechas.

    Returns
    -------
    Lista de dicts (una por serie configurada) con valor actual, variación y, si el
    modelo le asignó peso, su sentido/estabilidad. Series que fallan se omiten.
    """
    filas: list[dict] = []
    for spec in FRED_SERIES:
        try:
            serie = macro_source.get_series(spec.series_id, start, end)
        except Exception:
            # Sin clave FRED o error de red: omitimos esa serie (no rompemos el panel).
            continue
        if serie is None or serie.empty:
            continue

        valor = float(serie.iloc[-1])
        fecha = serie.index[-1].date().isoformat()
        variacion_abs = None
        variacion_pct = None
        if len(serie) > 1:
            previo = float(serie.iloc[-2])
            variacion_abs = valor - previo
            if previo != 0:
                variacion_pct = valor / previo - 1.0

        w = macro_weights.get(spec.nombre)
        filas.append(
            {
                "nombre": spec.nombre,
                "series_id": spec.series_id,
                "freq": spec.freq,
                "valor": valor,
                "fecha": fecha,
                "variacion_abs": variacion_abs,
                "variacion_pct": variacion_pct,
                "en_modelo": w is not None,
                "peso": (w or {}).get("peso"),
                "signo": (w or {}).get("signo"),
                "estabilidad": (w or {}).get("estabilidad"),
                "metodo": (w or {}).get("metodo"),
            }
        )
    return filas
