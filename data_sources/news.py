"""
Implementación de NewsDataSource con yfinance.
==============================================

Trae titulares recientes de Yahoo Finance asociados a un ticker. No requiere clave
(usa el mismo yfinance que los precios).

⚠️ ALCANCE Y ÉTICA DEL PRODUCTO:
Las noticias son CONTEXTO CUALITATIVO. NO se incorporan al modelo de retornos y NO se
usan para afirmar causalidad ("el precio subió por esta noticia"). Se muestran al lado
del análisis como posible trasfondo, separadas de los pesos estadísticos, para no
contradecir el lenguaje de asociación de la herramienta.

⚠️ LICENCIA: igual que los precios, yfinance/Yahoo es para desarrollo/investigación,
sin licencia para uso comercial. Para producción, migrar a un proveedor de noticias
con licencia creando otra clase NewsDataSource.
"""

from __future__ import annotations

from datetime import datetime, timezone

from data_sources.base import NewsDataSource, NewsItem


class YFinanceNewsSource(NewsDataSource):
    """Noticias recientes vía yfinance (Yahoo Finance)."""

    def get_news(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        ticker = ticker.upper().strip()

        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "yfinance no está instalado. Ejecutá: pip install -r requirements.txt"
            ) from exc

        try:
            crudas = yf.Ticker(ticker).news or []
        except Exception as exc:
            raise RuntimeError(
                f"Error de red obteniendo noticias de '{ticker}': {exc}"
            ) from exc

        items: list[NewsItem] = []
        for raw in crudas[: max(0, limit)]:
            item = self._parse(raw, ticker)
            if item is not None:
                items.append(item)
        return items

    @staticmethod
    def _parse(raw: dict, ticker: str) -> NewsItem | None:
        """Normaliza un item de yfinance a NewsItem.

        yfinance cambió el formato entre versiones:
        - Nuevo (>=0.2.40): los campos viven anidados en raw['content'].
        - Viejo: campos planos (title, publisher, link, providerPublishTime...).
        Soportamos ambos.
        """
        if not isinstance(raw, dict):
            return None

        contenido = raw.get("content")
        if isinstance(contenido, dict):
            # --- Formato nuevo (anidado) ---
            titulo = contenido.get("title") or ""
            resumen = contenido.get("summary") or contenido.get("description") or ""
            proveedor = (contenido.get("provider") or {}).get("displayName", "") or ""
            url = (
                (contenido.get("canonicalUrl") or {}).get("url")
                or (contenido.get("clickThroughUrl") or {}).get("url")
                or ""
            )
            publicado = contenido.get("pubDate") or contenido.get("displayTime") or ""
        else:
            # --- Formato viejo (plano) ---
            titulo = raw.get("title") or ""
            resumen = raw.get("summary") or ""
            proveedor = raw.get("publisher") or ""
            url = raw.get("link") or ""
            ts = raw.get("providerPublishTime")
            publicado = _epoch_a_iso(ts) if ts else ""

        if not titulo:
            return None  # sin título no aporta nada

        tickers = raw.get("relatedTickers") or []
        if ticker not in tickers:
            tickers = [ticker, *tickers]

        return NewsItem(
            titulo=titulo,
            fuente=proveedor,
            url=url,
            publicado=str(publicado),
            tickers=list(tickers),
            resumen=resumen,
        )


def _epoch_a_iso(ts: int | float) -> str:
    """Convierte un timestamp unix (segundos) a fecha/hora ISO legible (UTC)."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OSError):
        return ""
