"""
Implementaciones de MacroDataSource: FredSource y WorldBankSource.
==================================================================

- FredSource: series macro de EE.UU. vía fredapi (requiere FRED_API_KEY).
- WorldBankSource: indicadores macro por país vía la API pública del Banco Mundial
  (no requiere clave). Útil para extender el análisis a otros países.

Ambas devuelven la serie en su frecuencia NATIVA. El ajuste anti look-ahead
(desfase por fecha de publicación) se hace en pipeline/macro_align.py.
"""

from __future__ import annotations

import pandas as pd
import requests

from config.settings import SETTINGS, require_key
from data_sources import cache
from data_sources.base import MacroDataSource


class FredSource(MacroDataSource):
    """Series macro de FRED (Federal Reserve Economic Data)."""

    NAMESPACE = "macro_fred"

    def __init__(self, use_cache: bool = True) -> None:
        self.use_cache = use_cache
        self._fred = None  # inicialización perezosa

    def _client(self):
        """Crea el cliente fredapi validando la clave (falla explícito)."""
        if self._fred is None:
            api_key = require_key(
                SETTINGS.fred_api_key,
                "FRED_API_KEY",
                "Conseguila gratis en https://fredaccount.stlouisfed.org/apikeys",
            )
            try:
                from fredapi import Fred
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "fredapi no está instalado. Ejecutá: pip install -r requirements.txt"
                ) from exc
            self._fred = Fred(api_key=api_key)
        return self._fred

    def get_series(self, series_id: str, start: str, end: str) -> pd.Series:
        if self.use_cache:
            cached = cache.load(self.NAMESPACE, series_id, start, end)
            if cached is not None and not cached.empty:
                return cached.iloc[:, 0]

        fred = self._client()
        try:
            serie = fred.get_series(
                series_id, observation_start=start, observation_end=end
            )
        except Exception as exc:
            raise RuntimeError(
                f"Error obteniendo la serie FRED '{series_id}': {exc}"
            ) from exc

        if serie is None or serie.empty:
            raise RuntimeError(f"FRED no devolvió datos para la serie '{series_id}'.")

        serie.index = pd.to_datetime(serie.index)
        serie = serie.sort_index().dropna()
        serie.name = series_id

        if self.use_cache:
            cache.save(self.NAMESPACE, series_id, start, end, serie.to_frame())
        return serie


class WorldBankSource(MacroDataSource):
    """Indicadores macro por país vía la API pública del Banco Mundial.

    `series_id` se interpreta como "PAIS:INDICADOR" (ej. "USA:NY.GDP.MKTP.CD").
    Si no se especifica país, se asume USA. No requiere clave.
    """

    NAMESPACE = "macro_wb"
    BASE_URL = "https://api.worldbank.org/v2"

    def __init__(self, use_cache: bool = True) -> None:
        self.use_cache = use_cache

    def get_series(self, series_id: str, start: str, end: str) -> pd.Series:
        if ":" in series_id:
            country, indicator = series_id.split(":", 1)
        else:
            country, indicator = "USA", series_id

        if self.use_cache:
            cached = cache.load(self.NAMESPACE, series_id, start, end)
            if cached is not None and not cached.empty:
                return cached.iloc[:, 0]

        start_year = start[:4]
        end_year = end[:4]
        url = f"{self.BASE_URL}/country/{country}/indicator/{indicator}"
        params = {
            "format": "json",
            "date": f"{start_year}:{end_year}",
            "per_page": "20000",
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Error de red consultando World Bank ({series_id}): {exc}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError(
                f"World Bank devolvió una respuesta no-JSON para '{series_id}'."
            ) from exc

        # La API devuelve [metadata, datos]. Validamos la forma.
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            raise RuntimeError(
                f"World Bank no devolvió datos para '{series_id}'. "
                f"Verificá país/indicador."
            )

        registros = payload[1]
        fechas: list[pd.Timestamp] = []
        valores: list[float] = []
        for r in registros:
            if r.get("value") is None:
                continue
            # 'date' es el año (anual); lo fechamos al 31-dic de ese año.
            fechas.append(pd.Timestamp(f"{r['date']}-12-31"))
            valores.append(float(r["value"]))

        if not valores:
            raise RuntimeError(f"World Bank: serie '{series_id}' sin valores no nulos.")

        serie = pd.Series(valores, index=pd.DatetimeIndex(fechas), name=series_id)
        serie = serie.sort_index()

        if self.use_cache:
            cache.save(self.NAMESPACE, series_id, start, end, serie.to_frame())
        return serie
