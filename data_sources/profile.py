"""
Implementación de AssetProfileSource con yfinance.
==================================================

Trae la ficha descriptiva de un activo (identidad + fundamentals de referencia),
estilo finviz: sector, market cap, P/E, beta, márgenes, 52 semanas, etc.

⚠️ Son datos DESCRIPTIVOS de referencia, no señales del modelo ni recomendaciones.
⚠️ LICENCIA: yfinance/Yahoo es para desarrollo/investigación, sin licencia comercial.

Nota: `Ticker.info` hace una llamada de red y a veces es lento o devuelve campos
incompletos. Degradamos con gracia (campos faltantes → None) y usamos `fast_info`
como respaldo para precio/market cap.
"""

from __future__ import annotations

from data_sources.base import AssetProfile, AssetProfileSource


class YFinanceProfileSource(AssetProfileSource):
    """Ficha de activo vía yfinance."""

    def get_profile(self, ticker: str) -> AssetProfile:
        ticker = ticker.upper().strip()

        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "yfinance no está instalado. Ejecutá: pip install -r requirements.txt"
            ) from exc

        tk = yf.Ticker(ticker)

        # .info puede fallar/ser lento; lo envolvemos.
        info: dict = {}
        try:
            info = tk.info or {}
        except Exception:
            info = {}

        # fast_info como respaldo para precio / market cap / 52s.
        fast = {}
        try:
            fi = tk.fast_info
            fast = {
                "last_price": getattr(fi, "last_price", None),
                "market_cap": getattr(fi, "market_cap", None),
                "year_high": getattr(fi, "year_high", None),
                "year_low": getattr(fi, "year_low", None),
                "currency": getattr(fi, "currency", None),
            }
        except Exception:
            fast = {}

        def _num(*keys):
            """Primer valor numérico no nulo entre info[...] y fast[...]."""
            for src in (info, fast):
                for k in keys:
                    v = src.get(k)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        return float(v)
            return None

        def _str(*keys):
            for k in keys:
                v = info.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        if not info and not any(fast.values()):
            raise RuntimeError(
                f"yfinance no devolvió ficha para '{ticker}'. "
                f"¿El ticker es correcto y cotiza en EE.UU.?"
            )

        return AssetProfile(
            ticker=ticker,
            nombre=_str("longName", "shortName"),
            sector=_str("sector"),
            industria=_str("industry"),
            moneda=_str("currency") or fast.get("currency"),
            precio=_num("currentPrice", "regularMarketPrice", "last_price"),
            market_cap=_num("marketCap", "market_cap"),
            pe_trailing=_num("trailingPE"),
            pe_forward=_num("forwardPE"),
            beta=_num("beta"),
            margen_neto=_num("profitMargins"),
            dividend_yield=_num("dividendYield"),
            max_52s=_num("fiftyTwoWeekHigh", "year_high"),
            min_52s=_num("fiftyTwoWeekLow", "year_low"),
        )
