"""
Implementación de PriceDataSource con yfinance.
===============================================

⚠️ LICENCIA: yfinance obtiene datos de Yahoo Finance. Es apto para desarrollo,
investigación y validación, pero NO tiene licencia para uso comercial. Para
producción comercial hay que migrar a un proveedor con licencia (Polygon, EODHD,
etc.) — gracias al desacople, basta crear otra clase PriceDataSource.
"""

from __future__ import annotations

import pandas as pd

from data_sources import cache
from data_sources.base import PriceDataSource


class YFinanceSource(PriceDataSource):
    """Precios diarios vía yfinance, con cache local y manejo de errores."""

    NAMESPACE = "prices_yf"

    def __init__(self, use_cache: bool = True) -> None:
        self.use_cache = use_cache

    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        ticker = ticker.upper().strip()

        if self.use_cache:
            cached = cache.load(self.NAMESPACE, ticker, start, end)
            if cached is not None and not cached.empty:
                return cached

        # Import perezoso para que importar este módulo no exija yfinance instalado.
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "yfinance no está instalado. Ejecutá: pip install -r requirements.txt"
            ) from exc

        try:
            raw = yf.download(
                ticker,
                start=start,
                end=end,
                auto_adjust=True,   # 'Close' ya viene ajustado por splits/dividendos
                progress=False,
                threads=False,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Error de red descargando precios de '{ticker}' desde yfinance: {exc}"
            ) from exc

        if raw is None or raw.empty:
            raise RuntimeError(
                f"yfinance no devolvió datos para '{ticker}'. "
                f"¿El ticker es correcto y cotiza en EE.UU.?"
            )

        df = self._normalize(raw, ticker)

        if self.use_cache:
            cache.save(self.NAMESPACE, ticker, start, end, df)
        return df

    @staticmethod
    def _normalize(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Normaliza la salida de yfinance al contrato de PriceDataSource.

        yfinance a veces devuelve columnas MultiIndex (cuando hay varios tickers).
        Aplanamos y nos quedamos con un DataFrame de columnas en minúscula con
        'close' garantizada.
        """
        df = raw.copy()

        # Aplanar MultiIndex de columnas si aparece.
        if isinstance(df.columns, pd.MultiIndex):
            # Tomamos el primer nivel (Open/High/Low/Close/Volume).
            df.columns = df.columns.get_level_values(0)

        df.columns = [str(c).lower() for c in df.columns]

        if "close" not in df.columns:
            raise RuntimeError(
                f"Respuesta inesperada de yfinance para '{ticker}': "
                f"no hay columna 'close'. Columnas: {list(df.columns)}"
            )

        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        # Filas sin cierre no sirven.
        df = df.dropna(subset=["close"])
        return df
