"""
Estructuras de salida del modelado.
====================================

La salida por activo es un objeto estructurado y serializable. Es el ÚNICO contrato
que consume la capa de explicación (LLM): el modelo describe SOLO lo que hay acá.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class VariableWeight:
    """Peso de una variable sobre los retornos del activo.

    Attributes
    ----------
    variable : nombre legible (ej. "AMD (competidor)", "VIX (macro)").
    peso : magnitud del efecto estimado (coef. Lasso estandarizado o |SHAP| medio).
    signo : "+" si se mueve en el mismo sentido que el activo, "-" si opuesto.
    estabilidad : score en [0,1]; 1 = muy estable entre ventanas, 0 = muy inestable.
    metodo : "lasso" | "xgboost_shap" — de qué método salió este peso.
    descripcion : metadata de origen (rol/serie), opcional.
    """

    variable: str
    peso: float
    signo: str
    estabilidad: float
    metodo: str
    descripcion: str = ""


@dataclass
class ValidationReport:
    """Resultado de la validación out-of-sample vs baseline naive."""

    modelo: str                 # "lasso" | "xgboost_shap"
    metrica: str                # ej. "RMSE"
    error_modelo: float
    error_baseline_cero: float
    error_baseline_rezago: float
    aporta_sobre_baseline: bool
    n_splits: int
    nota: str = ""


@dataclass
class AssetResult:
    """Salida completa del análisis de un activo."""

    ticker: str
    variables: list[VariableWeight] = field(default_factory=list)
    validaciones: list[ValidationReport] = field(default_factory=list)
    n_observaciones: int = 0
    rango_fechas: tuple[str, str] = ("", "")

    def to_dict(self) -> dict:
        """Serializa a dict (para pasar al LLM o a la UI)."""
        return asdict(self)

    def top_variables(self, n: int = 15) -> list[VariableWeight]:
        """Variables ordenadas por |peso| descendente (las más asociadas primero)."""
        return sorted(self.variables, key=lambda v: abs(v.peso), reverse=True)[:n]
