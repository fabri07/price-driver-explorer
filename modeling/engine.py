"""
Orquestador de modelado: combina Lasso + XGBoost/SHAP en un AssetResult.
========================================================================

Toma un AssetDataset (X, y) y produce el objeto estructurado final que consume la
capa de explicación y la UI. Corre ambos métodos complementarios y los etiqueta.
"""

from __future__ import annotations

from pipeline.dataset import AssetDataset
from modeling.lasso_model import fit_lasso
from modeling.random_forest import fit_rf_shap
from modeling.results import AssetResult, VariableWeight
from modeling.xgb_shap import fit_xgb_shap


def analyze(dataset: AssetDataset, *, run_xgb: bool = True, run_rf: bool = True) -> AssetResult:
    """Corre el análisis completo sobre un dataset ya ensamblado.

    Parameters
    ----------
    dataset : AssetDataset con X, y y metadata.
    run_xgb : si False, omite XGBoost/SHAP (más rápido).
    run_rf : si False, omite RandomForest/SHAP (más rápido). El tercer método actúa
        como desempate entre Lasso (lineal) y XGBoost (boosting).

    Returns
    -------
    AssetResult con la lista combinada de pesos y los reportes de validación.
    """
    X, y = dataset.X, dataset.y

    if X.empty or len(X.columns) == 0:
        raise ValueError(
            f"Dataset vacío para {dataset.ticker}: no hay features utilizables tras "
            f"la limpieza. Revisá fechas/tickers/macro."
        )

    variables: list[VariableWeight] = []
    validaciones = []

    # --- Método 1: Lasso --------------------------------------------------
    pesos_lasso, val_lasso = fit_lasso(X, y)
    variables.extend(_inject_meta(pesos_lasso, dataset))
    validaciones.append(val_lasso)

    # --- Método 2: XGBoost + SHAP ----------------------------------------
    if run_xgb:
        try:
            pesos_xgb, val_xgb = fit_xgb_shap(X, y)
            variables.extend(_inject_meta(pesos_xgb, dataset))
            validaciones.append(val_xgb)
        except Exception as exc:
            # XGBoost/SHAP es opcional; si falla, seguimos con los demás.
            print(f"  [aviso] XGBoost/SHAP falló, lo omito: {exc}")

    # --- Método 3: RandomForest + SHAP (desempate por bagging) -----------
    if run_rf:
        try:
            pesos_rf, val_rf = fit_rf_shap(X, y)
            variables.extend(_inject_meta(pesos_rf, dataset))
            validaciones.append(val_rf)
        except Exception as exc:
            # RandomForest/SHAP es opcional; si falla, seguimos con los demás.
            print(f"  [aviso] RandomForest/SHAP falló, lo omito: {exc}")

    rango = (
        X.index.min().date().isoformat(),
        X.index.max().date().isoformat(),
    )

    return AssetResult(
        ticker=dataset.ticker,
        variables=variables,
        validaciones=validaciones,
        n_observaciones=len(X),
        rango_fechas=rango,
    )


def _inject_meta(pesos: list[VariableWeight], dataset: AssetDataset) -> list[VariableWeight]:
    """Rellena la descripción de cada peso con la metadata de origen del dataset."""
    for p in pesos:
        p.descripcion = dataset.feature_meta.get(p.variable, "")
    return pesos
