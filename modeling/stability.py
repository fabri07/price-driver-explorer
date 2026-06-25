"""
Estabilidad de los pesos vía bootstrap sobre ventanas móviles.
==============================================================

Un peso estimado sobre TODO el período puede ser un artefacto de una época puntual.
Para medir cuán confiable es cada peso, lo re-estimamos en muchas sub-ventanas
(bootstrap por bloques temporales) y miramos su dispersión.

Score de estabilidad ∈ [0,1]:
  estabilidad = 1 - (desvío_de_pesos / (|peso_medio| + desvío_de_pesos))
- ~1: el peso es consistente entre ventanas (signo y magnitud estables).
- ~0: el peso cambia mucho (poco confiable; tratar como ruido).

Este score alimenta la UI (banda de incertidumbre) y el prompt del LLM (advertir
cuando la estabilidad es baja).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def block_bootstrap_indices(
    n: int, window: int, n_resamples: int, rng: np.random.Generator
) -> list[np.ndarray]:
    """Genera índices de sub-ventanas contiguas (bloques) para bootstrap temporal.

    Usar bloques contiguos (en vez de muestreo i.i.d.) respeta la autocorrelación
    de series temporales.
    """
    if window >= n:
        # Serie corta: una sola ventana = todo.
        return [np.arange(n)]
    max_start = n - window
    starts = rng.integers(0, max_start + 1, size=n_resamples)
    return [np.arange(s, s + window) for s in starts]


def weight_stability(
    coef_fn,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    window_frac: float = 0.5,
    n_resamples: int = 30,
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    """Estima estabilidad de cada peso re-corriendo el modelo en sub-ventanas.

    Parameters
    ----------
    coef_fn : callable (X_sub, y_sub) -> dict {variable -> coeficiente}.
        Encapsula el ajuste de un modelo y la extracción de sus pesos.
    X, y : dataset completo.
    window_frac : tamaño de cada ventana como fracción del total.
    n_resamples : cantidad de ventanas bootstrap.
    seed : semilla (reproducibilidad; evitamos aleatoriedad no controlada).

    Returns
    -------
    dict {variable -> {"peso_medio", "desvio", "estabilidad"}}.
    """
    n = len(X)
    window = max(30, int(n * window_frac))
    rng = np.random.default_rng(seed)
    bloques = block_bootstrap_indices(n, window, n_resamples, rng)

    acumulado: dict[str, list[float]] = {col: [] for col in X.columns}

    for idx in bloques:
        X_sub = X.iloc[idx]
        y_sub = y.iloc[idx]
        try:
            coefs = coef_fn(X_sub, y_sub)
        except Exception:
            # Una ventana degenerada no debe romper el bootstrap completo.
            continue
        for col in X.columns:
            acumulado[col].append(float(coefs.get(col, 0.0)))

    resultado: dict[str, dict[str, float]] = {}
    for col, valores in acumulado.items():
        arr = np.array(valores) if valores else np.array([0.0])
        peso_medio = float(np.mean(arr))
        desvio = float(np.std(arr))
        denom = abs(peso_medio) + desvio
        estabilidad = float(1.0 - desvio / denom) if denom > 1e-12 else 0.0
        estabilidad = max(0.0, min(1.0, estabilidad))
        resultado[col] = {
            "peso_medio": peso_medio,
            "desvio": desvio,
            "estabilidad": estabilidad,
        }
    return resultado
