"""
Orquestador end-to-end (CLI).
=============================

Corre el pipeline completo para un activo SIN levantar la UI: descarga datos,
modela, valida y (opcionalmente) genera el resumen del LLM. Sirve para validar la
base punta a punta.

Uso:
    python run_analysis.py NVDA
    python run_analysis.py GOOGL --sin-resumen     # omite la llamada al LLM
    python run_analysis.py TSLA --sin-xgb          # solo Lasso (más rápido)
    python run_analysis.py NVDA --noticias         # agrega noticias recientes

La función `run_full_analysis` también la reutiliza la app Streamlit.
"""

from __future__ import annotations

import argparse
import sys

# La consola de Windows suele ser cp1252 y no puede codificar algunos caracteres
# (flechas, símbolos). Forzamos UTF-8 con reemplazo para que el CLI nunca crashee
# por encoding. (En consolas legacy puede verse algún carácter raro, pero no rompe.)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

from config.relationship_graph import TICKERS_OBJETIVO
from data_sources.macro import FredSource
from data_sources.prices import YFinanceSource
from modeling import engine
from modeling.results import AssetResult
from pipeline.dataset import build_dataset


def run_full_analysis(
    target: str,
    *,
    include_macro: bool = True,
    run_xgb: bool = True,
    run_rf: bool = True,
    use_cache: bool = True,
) -> AssetResult:
    """Ejecuta dataset + modelado y devuelve el AssetResult (sin LLM).

    Las fuentes de datos se inyectan acá (desacople): cambiar de proveedor es
    cambiar estas dos líneas.
    """
    price_source = YFinanceSource(use_cache=use_cache)
    macro_source = FredSource(use_cache=use_cache) if include_macro else None

    print(f"[1/3] Descargando y ensamblando datos para {target}...")
    dataset = build_dataset(
        target,
        price_source=price_source,
        macro_source=macro_source,
        include_macro=include_macro,
    )
    print(f"      Dataset: {dataset.X.shape[0]} filas, {dataset.X.shape[1]} features.")

    metodos = "Lasso" + (" + XGBoost/SHAP" if run_xgb else "") + (" + RandomForest/SHAP" if run_rf else "")
    print(f"[2/3] Modelando ({metodos})...")
    result = engine.analyze(dataset, run_xgb=run_xgb, run_rf=run_rf)

    print("[3/3] Listo.")
    return result


def _print_result(result: AssetResult) -> None:
    """Imprime el AssetResult de forma legible en consola."""
    print("\n" + "=" * 60)
    print(f"RESULTADO — {result.ticker}")
    print(f"Período: {result.rango_fechas[0]} a {result.rango_fechas[1]} "
          f"({result.n_observaciones} obs.)")
    print("=" * 60)

    for val in result.validaciones:
        aporta = "SI aporta" if val.aporta_sobre_baseline else "NO aporta"
        print(f"\n[{val.modelo}] {val.metrica}={val.error_modelo:.6f} "
              f"(baseline cero={val.error_baseline_cero:.6f}, "
              f"rezago={val.error_baseline_rezago:.6f}) -> {aporta} sobre baseline")

    print("\nTop variables (por |peso|):")
    for v in result.top_variables(n=15):
        sentido = "+" if v.signo == "+" else "-"
        print(f"  [{v.metodo:>13}] {sentido} {v.peso:.4f} "
              f"(estab. {v.estabilidad:.2f})  {v.variable}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Análisis de asociaciones de un activo.")
    parser.add_argument("ticker", help=f"Activo objetivo (ej. {', '.join(TICKERS_OBJETIVO)})")
    parser.add_argument("--sin-resumen", action="store_true", help="No llamar al LLM.")
    parser.add_argument("--sin-xgb", action="store_true", help="Omite XGBoost/SHAP.")
    parser.add_argument("--sin-rf", action="store_true", help="Omite RandomForest/SHAP.")
    parser.add_argument("--sin-macro", action="store_true", help="Omite variables macro (FRED).")
    parser.add_argument("--noticias", action="store_true", help="Muestra noticias recientes del activo.")
    args = parser.parse_args(argv)

    try:
        result = run_full_analysis(
            args.ticker.upper(),
            include_macro=not args.sin_macro,
            run_xgb=not args.sin_xgb,
            run_rf=not args.sin_rf,
        )
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    _print_result(result)

    if args.noticias:
        print("\n" + "-" * 60)
        print("NOTICIAS RECIENTES (contexto cualitativo, fuera del modelo)")
        print("-" * 60)
        try:
            from data_sources.news import YFinanceNewsSource

            noticias = YFinanceNewsSource().get_news(args.ticker.upper(), limit=10)
            if not noticias:
                print("(sin noticias recientes disponibles)")
            for n in noticias:
                meta = " · ".join(p for p in [n.fuente, n.publicado] if p)
                print(f"\n• {n.titulo}")
                if meta:
                    print(f"  {meta}")
                if n.url:
                    print(f"  {n.url}")
        except Exception as exc:
            print(f"[aviso] No se pudieron cargar las noticias: {exc}", file=sys.stderr)

    if not args.sin_resumen:
        print("\nGenerando resumen en lenguaje natural (LLM)...")
        try:
            from explanation.llm_explainer import generate_summary

            resumen = generate_summary(result)
            print("\n" + "-" * 60)
            print("RESUMEN")
            print("-" * 60)
            print(resumen)
        except Exception as exc:
            print(f"\n[aviso] No se pudo generar el resumen: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
