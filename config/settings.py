"""
Configuración central: carga de .env, claves y parámetros globales.
===================================================================

Política de claves (decisión de diseño: FALLAR EXPLÍCITO):
- yfinance y World Bank NO requieren clave.
- FRED requiere FRED_API_KEY.
- Anthropic requiere ANTHROPIC_API_KEY.
- SEC EDGAR requiere un User-Agent con email de contacto (SEC_USER_AGENT).

Si una funcionalidad necesita una clave ausente, `require_key()` lanza ConfigError
con un mensaje claro en vez de degradar silenciosamente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Carga .env desde la raíz del proyecto. override=True: el .env es la fuente de
# verdad y PISA cualquier variable del sistema con el mismo nombre (evita que una
# variable vieja/placeholder del entorno opaque tu clave real del .env).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)


class ConfigError(RuntimeError):
    """Error de configuración (clave faltante, valor inválido, etc.)."""


@dataclass(frozen=True)
class Settings:
    """Parámetros globales de la app, leídos del entorno con defaults sensatos."""

    # --- Claves (pueden ser None; se validan al usarse vía require_key) ---
    fred_api_key: str | None
    anthropic_api_key: str | None
    sec_user_agent: str | None

    # --- LLM --------------------------------------------------------------
    # Modelo configurable vía ANTHROPIC_MODEL. Default: Opus 4.8 (máxima calidad).
    # Para bajar costo en producción de alto volumen, poné claude-sonnet-4-6 en .env.
    anthropic_model: str

    # --- Ventana de datos -------------------------------------------------
    start_date: str   # ISO yyyy-mm-dd
    end_date: str     # ISO yyyy-mm-dd

    # --- Infraestructura --------------------------------------------------
    cache_dir: Path
    project_root: Path


def _default_dates(years: int = 5) -> tuple[str, str]:
    """Ventana por defecto: últimos `years` años hasta hoy."""
    today = date.today()
    start = today - timedelta(days=365 * years)
    return start.isoformat(), today.isoformat()


def load_settings() -> Settings:
    """Construye Settings a partir de variables de entorno (.env)."""
    default_start, default_end = _default_dates()
    cache_dir = _PROJECT_ROOT / ".cache"

    return Settings(
        fred_api_key=os.getenv("FRED_API_KEY") or None,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        sec_user_agent=os.getenv("SEC_USER_AGENT") or None,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"),
        start_date=os.getenv("START_DATE", default_start),
        end_date=os.getenv("END_DATE", default_end),
        cache_dir=Path(os.getenv("CACHE_DIR", str(cache_dir))),
        project_root=_PROJECT_ROOT,
    )


# Instancia única reutilizable.
SETTINGS = load_settings()


def require_key(value: str | None, name: str, ayuda: str) -> str:
    """Devuelve `value` o lanza ConfigError con un mensaje accionable.

    Parameters
    ----------
    value : el valor leído del entorno (posiblemente None/"").
    name  : nombre de la variable (ej. "FRED_API_KEY").
    ayuda : instrucción concreta de cómo obtenerla.
    """
    if not value:
        raise ConfigError(
            f"Falta la variable de entorno {name}.\n"
            f"  → {ayuda}\n"
            f"  Configurala en el archivo .env (ver .env.example)."
        )
    return value
