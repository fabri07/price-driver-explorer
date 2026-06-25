"""
Implementación de FundamentalsSource con SEC EDGAR.
===================================================

Descarga fundamentals (companyfacts) de empresas que reportan a la SEC de EE.UU.

⚠️ La SEC EXIGE un header User-Agent identificando al usuario (nombre + email).
Sin él, devuelve 403. Se configura en .env como SEC_USER_AGENT.

ALCANCE EN ESTA BASE: fetch básico funcional (mapeo ticker→CIK + companyfacts).
NO se integra al modelo de retornos diarios (los fundamentals son trimestrales y no
encajan en esa frecuencia). Queda disponible para inspección cualitativa o para
extender el modelo a futuro.
"""

from __future__ import annotations

import json

import requests

from config.settings import SETTINGS, require_key
from data_sources.base import FundamentalsSource

# Endpoints públicos de la SEC.
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


class SecEdgarSource(FundamentalsSource):
    """Fundamentals vía la API XBRL de SEC EDGAR."""

    def __init__(self) -> None:
        self._ticker_to_cik: dict[str, int] | None = None

    def _headers(self) -> dict[str, str]:
        """Headers con el User-Agent obligatorio (falla explícito si falta)."""
        ua = require_key(
            SETTINGS.sec_user_agent,
            "SEC_USER_AGENT",
            'Definí un User-Agent con tu email, ej. "Mi App ejemplo@dominio.com". '
            "La SEC lo exige para usar su API.",
        )
        return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}

    def _load_ticker_map(self) -> dict[str, int]:
        """Descarga y cachea en memoria el mapeo ticker→CIK de la SEC."""
        if self._ticker_to_cik is not None:
            return self._ticker_to_cik

        try:
            resp = requests.get(_TICKER_MAP_URL, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Error de red descargando el mapeo ticker→CIK de la SEC: {exc}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError("SEC devolvió un mapeo ticker→CIK no-JSON.") from exc

        mapping: dict[str, int] = {}
        # El JSON es {"0": {"cik_str": 320193, "ticker": "AAPL", ...}, ...}
        for entry in data.values():
            mapping[str(entry["ticker"]).upper()] = int(entry["cik_str"])
        self._ticker_to_cik = mapping
        return mapping

    def get_facts(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        mapping = self._load_ticker_map()

        if ticker not in mapping:
            raise RuntimeError(
                f"'{ticker}' no aparece en el listado de la SEC. "
                f"¿Es una empresa que reporta en EE.UU.?"
            )

        cik = mapping[ticker]
        url = _COMPANYFACTS_URL.format(cik=cik)
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Error de red obteniendo companyfacts de '{ticker}' (CIK {cik}): {exc}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError(
                f"SEC devolvió companyfacts no-JSON para '{ticker}'."
            ) from exc

    def get_concept_latest(self, ticker: str, concept: str = "Revenues") -> dict | None:
        """Helper de conveniencia: último valor reportado de un concepto US-GAAP.

        Ejemplo de uso de los facts; devuelve {'valor', 'fin', 'unidad'} o None.
        No se usa en el modelo diario; es ilustrativo.
        """
        facts = self.get_facts(ticker)
        try:
            unidades = facts["facts"]["us-gaap"][concept]["units"]
        except (KeyError, TypeError):
            return None

        # Tomamos la primera unidad (ej. "USD") y su última observación.
        for unidad, observaciones in unidades.items():
            if not observaciones:
                continue
            ultima = sorted(observaciones, key=lambda o: o.get("end", ""))[-1]
            return {
                "valor": ultima.get("val"),
                "fin": ultima.get("end"),
                "unidad": unidad,
            }
        return None


if __name__ == "__main__":  # pequeña prueba manual
    src = SecEdgarSource()
    print(json.dumps(src.get_concept_latest("NVDA", "Revenues"), indent=2))
