"""
Cache local en parquet para acelerar la iteración de desarrollo.
================================================================

Evita re-descargar los mismos datos en cada corrida. La cache es por (namespace,
clave, rango de fechas). Para invalidarla, borrá la carpeta `.cache/`.

No es una cache "de producción" (sin TTL ni invalidación inteligente): es una ayuda
de desarrollo. Si necesitás datos frescos, borrá la carpeta.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from config.settings import SETTINGS


def _key_path(namespace: str, key: str, start: str, end: str) -> Path:
    """Ruta del archivo parquet para una entrada de cache."""
    raw = f"{namespace}|{key}|{start}|{end}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    safe_key = "".join(c if c.isalnum() else "_" for c in key)[:40]
    folder = SETTINGS.cache_dir / namespace
    return folder / f"{safe_key}_{digest}.parquet"


def load(namespace: str, key: str, start: str, end: str) -> pd.DataFrame | None:
    """Devuelve un DataFrame cacheado o None si no existe / falla la lectura."""
    path = _key_path(namespace, key, start, end)
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        # Cache corrupta: la ignoramos (se regenera).
        return None


def save(namespace: str, key: str, start: str, end: str, df: pd.DataFrame) -> None:
    """Guarda un DataFrame en cache. Silencioso ante errores (cache es best-effort)."""
    path = _key_path(namespace, key, start, end)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
    except Exception:
        # Si no se puede cachear (ej. falta pyarrow), seguimos sin romper.
        pass
