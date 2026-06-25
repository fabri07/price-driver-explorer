"""
Ensamblado del dataset por activo: X (features) e y (target).
=============================================================

Orquesta fuentes de datos + transformaciones del pipeline para producir el par
(X, y) listo para modelar, manteniendo el desacople: recibe las fuentes por
inyección de dependencias (interfaces abstractas), no las instancia internamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config.fred_series import FRED_SERIES
from config.relationship_graph import all_feature_tickers, feature_role
from config.settings import SETTINGS
from data_sources.base import MacroDataSource, PriceDataSource
from pipeline import alignment, macro_align
from pipeline.returns import returns_from_price_df


@dataclass
class AssetDataset:
    """Resultado del ensamblado para un activo objetivo."""

    ticker: str
    X: pd.DataFrame              # features alineados y limpios
    y: pd.Series                 # target (retornos log del activo objetivo)
    feature_meta: dict[str, str] = field(default_factory=dict)  # nombre -> rol/origen


def _feature_name_price(ticker: str, target: str) -> str:
    """Nombre legible de una columna de retorno de un activo de contexto."""
    return f"{ticker} ({feature_role(target, ticker)})"


def build_dataset(
    target: str,
    price_source: PriceDataSource,
    macro_source: MacroDataSource | None,
    *,
    start: str | None = None,
    end: str | None = None,
    include_macro: bool = True,
) -> AssetDataset:
    """Construye (X, y) para `target`.

    Parameters
    ----------
    target : ticker del activo objetivo.
    price_source : implementación de PriceDataSource (inyectada).
    macro_source : implementación de MacroDataSource (inyectada). Si include_macro
        es True, es obligatoria.
    start, end : ventana de fechas (default: SETTINGS).
    include_macro : si False, omite las series macro (útil para tests rápidos).
    """
    start = start or SETTINGS.start_date
    end = end or SETTINGS.end_date

    # --- Target -----------------------------------------------------------
    target_prices = price_source.get_history(target, start, end)
    y = returns_from_price_df(target_prices)
    y = alignment.winsorize(y)
    y.name = f"retorno_{target}"

    feature_meta: dict[str, str] = {}

    # --- Features de activos de contexto ---------------------------------
    feature_frames: dict[str, pd.Series] = {}
    for tk in all_feature_tickers(target):
        try:
            px = price_source.get_history(tk, start, end)
        except Exception as exc:
            # Un activo de contexto que falla no debe tumbar todo el análisis.
            print(f"  [aviso] omito '{tk}' (no se pudo descargar): {exc}")
            continue
        r = alignment.winsorize(returns_from_price_df(px))
        nombre = _feature_name_price(tk, target)
        feature_frames[nombre] = r
        feature_meta[nombre] = f"retorno de {tk} — {feature_role(target, tk)}"

    # --- Features macro (anti look-ahead) --------------------------------
    macro_frames: dict[str, pd.Series] = {}
    if include_macro:
        if macro_source is None:
            raise ValueError("include_macro=True requiere un macro_source.")
        market_calendar = y.index
        for spec in FRED_SERIES:
            try:
                serie = macro_source.get_series(spec.series_id, start, end)
            except Exception as exc:
                print(f"  [aviso] omito serie macro '{spec.series_id}': {exc}")
                continue
            alineada = macro_align.align_macro_no_lookahead(
                serie,
                spec.publication_lag_days,
                market_calendar,
                transformacion=spec.transformacion,
                freq=spec.freq,
            )
            macro_frames[spec.nombre] = alineada
            feature_meta[spec.nombre] = f"macro: {spec.nombre} ({spec.freq})"

    # --- Alineación + limpieza -------------------------------------------
    X = alignment.align_features_to_target(y, feature_frames, macro_frames)
    X = alignment.drop_sparse_columns(X)
    X, y = alignment.finalize_dataset(X, y)

    # Filtrar metadata a las columnas que sobrevivieron.
    feature_meta = {k: v for k, v in feature_meta.items() if k in X.columns}

    return AssetDataset(ticker=target, X=X, y=y, feature_meta=feature_meta)
