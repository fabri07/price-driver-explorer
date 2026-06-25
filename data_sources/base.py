"""
Interfaces abstractas de fuentes de datos.
==========================================

★ DESACOPLE DE FUENTES (decisión de arquitectura central) ★

El resto del proyecto (pipeline, modeling, app) depende SOLO de estas interfaces,
nunca de yfinance / FRED / SEC directamente. Para cambiar de proveedor mañana
(Polygon, EODHD, etc.) se crea una clase nueva que implemente la interfaz y se
inyecta — sin tocar nada más.

Contratos
---------
- PriceDataSource.get_history -> DataFrame con DatetimeIndex y columna 'close'.
- MacroDataSource.get_series  -> Series con DatetimeIndex (frecuencia nativa).
- FundamentalsSource.get_facts -> dict de hechos contables (forma libre por proveedor).
- NewsDataSource.get_news -> lista de NewsItem (contexto cualitativo, NO modelado).
- AssetProfileSource.get_profile -> AssetProfile (ficha tipo finviz, descriptiva).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


class PriceDataSource(ABC):
    """Fuente de precios históricos de un activo."""

    @abstractmethod
    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Historial de precios de `ticker` entre `start` y `end` (ISO yyyy-mm-dd).

        Returns
        -------
        DataFrame con:
          - índice: DatetimeIndex (días de mercado), ordenado ascendente.
          - columna obligatoria: 'close' (precio de cierre ajustado, float).
          - opcionalmente: 'open', 'high', 'low', 'volume'.

        Debe lanzar una excepción clara si el ticker no existe o falla la red.
        """
        raise NotImplementedError


class MacroDataSource(ABC):
    """Fuente de series macroeconómicas."""

    @abstractmethod
    def get_series(self, series_id: str, start: str, end: str) -> pd.Series:
        """Serie macro `series_id` entre `start` y `end`.

        Returns
        -------
        Series con DatetimeIndex en su frecuencia NATIVA (diaria/mensual/trimestral),
        fechada por período de referencia. El ajuste anti look-ahead se hace después,
        en el pipeline, NO acá.
        """
        raise NotImplementedError


class FundamentalsSource(ABC):
    """Fuente de fundamentals (estados contables) de una empresa."""

    @abstractmethod
    def get_facts(self, ticker: str) -> dict:
        """Hechos contables de `ticker`.

        La forma exacta depende del proveedor (en esta base, SEC EDGAR). No se
        integra al modelo diario; queda disponible para análisis cualitativo.
        """
        raise NotImplementedError


@dataclass
class NewsItem:
    """Una noticia financiera asociada a un activo.

    Es CONTEXTO CUALITATIVO: no entra al modelo de retornos ni se usa para afirmar
    causalidad. Solo se muestra junto al análisis como posible trasfondo.
    """

    titulo: str
    fuente: str                          # editor/publisher
    url: str
    publicado: str                       # fecha/hora legible (ISO o texto)
    tickers: list[str] = field(default_factory=list)  # tickers relacionados
    resumen: str = ""                    # bajada/resumen, si el proveedor lo da


class NewsDataSource(ABC):
    """Fuente de noticias financieras de un activo."""

    @abstractmethod
    def get_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        """Noticias recientes asociadas a `ticker` (más nuevas primero).

        Devuelve hasta `limit` `NewsItem`. Es contexto cualitativo: NO alimenta el
        modelo. Debe manejar errores de red devolviendo una lista vacía o lanzando
        una excepción clara, según la implementación.
        """
        raise NotImplementedError


@dataclass
class AssetProfile:
    """Ficha descriptiva de un activo (estilo finviz).

    Datos de referencia (fundamentals/identidad), DESCRIPTIVOS — no son señales del
    modelo ni recomendaciones. Cualquier campo puede ser None si el proveedor no lo
    informa.
    """

    ticker: str
    nombre: str | None = None              # razón social
    sector: str | None = None
    industria: str | None = None
    moneda: str | None = None
    precio: float | None = None            # último precio
    market_cap: float | None = None
    pe_trailing: float | None = None       # P/E (12m)
    pe_forward: float | None = None        # P/E proyectado
    beta: float | None = None              # beta informado por el proveedor
    margen_neto: float | None = None       # profit margin (0-1)
    dividend_yield: float | None = None    # 0-1
    max_52s: float | None = None           # máximo 52 semanas
    min_52s: float | None = None           # mínimo 52 semanas
    extra: dict = field(default_factory=dict)  # campos crudos adicionales


class AssetProfileSource(ABC):
    """Fuente de la ficha descriptiva (fundamentals/identidad) de un activo."""

    @abstractmethod
    def get_profile(self, ticker: str) -> AssetProfile:
        """Ficha de `ticker`. Descriptiva, no es señal del modelo.

        Debe degradar con gracia: si un campo no está disponible, queda None
        (no lanzar por campos faltantes; sí ante fallas de red claras).
        """
        raise NotImplementedError
