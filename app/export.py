"""
Exportación del resumen.
=========================

Por ahora exportamos a Markdown (cero dependencias del sistema). `to_pdf` queda como
stub documentado: el hook está listo para cuando se quiera agregar PDF con una librería
pure-Python (reportlab / fpdf2) o vía HTML→PDF.
"""

from __future__ import annotations

from modeling.results import AssetResult

# Disclaimer fijo del producto (también se muestra en la UI).
DISCLAIMER = (
    "Herramienta educativa. No es asesoramiento de inversión. "
    "Describe asociaciones históricas, no predicciones."
)


def to_markdown(result: AssetResult, resumen: str) -> str:
    """Arma el resumen completo en Markdown (descargable).

    Incluye: título, disclaimer, el resumen del LLM, la tabla de variables y el
    reporte de validación.
    """
    lineas: list[str] = []
    lineas.append(f"# Análisis de asociaciones — {result.ticker}")
    lineas.append("")
    lineas.append(f"> **{DISCLAIMER}**")
    lineas.append("")
    lineas.append(
        f"Período analizado: {result.rango_fechas[0]} a {result.rango_fechas[1]} "
        f"({result.n_observaciones} días de mercado)."
    )
    lineas.append("")

    # --- Resumen en lenguaje natural ---
    lineas.append("## Resumen")
    lineas.append("")
    lineas.append(resumen)
    lineas.append("")

    # --- Tabla de variables ---
    lineas.append("## Variables y pesos")
    lineas.append("")
    lineas.append("| Método | Variable | Peso | Sentido | Estabilidad |")
    lineas.append("|---|---|---:|:---:|---:|")
    for v in result.top_variables(n=30):
        sentido = "mismo" if v.signo == "+" else "opuesto"
        lineas.append(
            f"| {v.metodo} | {v.variable} | {v.peso:.4f} | {sentido} | {v.estabilidad:.2f} |"
        )
    lineas.append("")

    # --- Validación ---
    lineas.append("## Validación (out-of-sample vs baseline)")
    lineas.append("")
    for val in result.validaciones:
        aporta = "Sí" if val.aporta_sobre_baseline else "No"
        lineas.append(f"### Método: {val.modelo}")
        lineas.append("")
        lineas.append(f"- {val.metrica} modelo: {val.error_modelo:.6f}")
        lineas.append(f"- {val.metrica} baseline (cero): {val.error_baseline_cero:.6f}")
        lineas.append(f"- {val.metrica} baseline (rezago): {val.error_baseline_rezago:.6f}")
        lineas.append(f"- **¿Aporta sobre el baseline?** {aporta}")
        if val.nota:
            lineas.append(f"- Nota: {val.nota}")
        lineas.append("")

    lineas.append("---")
    lineas.append(f"_{DISCLAIMER}_")
    lineas.append("")

    return "\n".join(lineas)


def to_pdf(result: AssetResult, resumen: str) -> bytes:  # pragma: no cover
    """STUB: exportación a PDF (hook para implementar después).

    Decisión de diseño: en esta base el botón de descarga usa Markdown (sin
    dependencias del sistema). Para PDF, opciones recomendadas en Windows:
      - fpdf2 (pure-Python, simple),
      - reportlab (pure-Python, más control),
      - markdown -> HTML -> PDF con weasyprint (requiere GTK; evitar en Windows).

    Implementación sugerida: render del Markdown de `to_markdown(...)` a PDF.
    """
    raise NotImplementedError(
        "Exportación a PDF no implementada todavía. Usá la descarga en Markdown. "
        "Ver el docstring de to_pdf() para opciones de implementación."
    )
