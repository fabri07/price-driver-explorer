"""
Interfaz Streamlit.
===================

Selector de activo → corre el pipeline → muestra los resultados en pestañas:
  - 📊 Asociaciones: pesos del modelo + validación + resumen del LLM + descarga.
  - 🏢 Overview: ficha tipo finviz (fundamentals) + desempeño + gráfico de precio.
  - 🌐 Macro: valores actuales de FRED + el peso que el modelo les asignó.
  - 📰 Noticias: titulares recientes (contexto cualitativo).
Disclaimer fijo y visible arriba de todo.

Ejecutar con:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permitir importar los módulos del proyecto al correr `streamlit run app/...`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app import charts, export
from config.fred_series import glosa_por_nombre
from config.relationship_graph import (
    RELATIONSHIP_GRAPH,
    TICKERS_OBJETIVO,
    all_feature_tickers,
    entidades_no_listadas,
)
from config.settings import SETTINGS
from modeling.results import AssetResult
from run_analysis import run_full_analysis

st.set_page_config(page_title="Asociaciones de precio (educativo)", layout="wide")


def _inject_estilo_terminal() -> None:
    """Identidad 'terminal de trading': negro + verde fósforo.

    - Tipografía: 'Playfair Display' en encabezados de sección, 'IBM Plex Mono' en datos
      y en el hero (look de terminal), 'Inter' en el cuerpo.
    - Acento verde fósforo (#00D982) en foco, tabs activos, botones y reglas.
    - El rojo se reserva para 'sentido opuesto / baja' (convención financiera).
    Los colores base viven en .streamlit/config.toml; acá va el detalle fino.
    """
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        :root {
            --verde: #00D982;
            --verde-tenue: rgba(0,217,130,0.14);
            --negro: #0A0F0C;
            --panel: #111815;
            --papel: #E4EDE8;
        }

        /* Encabezados de sección: serif editorial */
        h2, h3, h4, h5,
        [data-testid="stHeading"] {
            font-family: 'Playfair Display', Georgia, serif !important;
            letter-spacing: 0.2px;
        }

        /* Cuerpo de texto */
        html, body, p, span, label, li,
        .stMarkdown, [data-testid="stCaptionContainer"], .stRadio, .stCheckbox {
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* Datos numéricos: monospace de terminal */
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"],
        [data-testid="stDataFrame"] *,
        code, .stCode {
            font-family: 'IBM Plex Mono', 'SFMono-Regular', monospace !important;
        }
        [data-testid="stMetricValue"] { color: var(--papel) !important; }
        [data-testid="stMetricLabel"] {
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-size: 0.72rem !important;
            opacity: 0.7;
        }
        /* Métricas como 'tickets' con regla verde a la izquierda */
        [data-testid="stMetric"] {
            background: var(--panel);
            border-left: 2px solid var(--verde);
            border-radius: 2px;
            padding: 0.5rem 0.75rem;
        }

        /* ===== HERO: el título como un prompt de terminal ===== */
        .hero { margin: 0.2rem 0 1.1rem 0; }
        .hero-eyebrow {
            font-family: 'IBM Plex Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 2.4px;
            font-size: 0.7rem;
            color: var(--verde);
            opacity: 0.85;
            margin-bottom: 0.35rem;
        }
        .hero-q {
            font-family: 'IBM Plex Mono', 'SFMono-Regular', monospace !important;
            font-weight: 600;
            font-size: clamp(1.5rem, 3.4vw, 2.55rem);
            line-height: 1.15;
            color: var(--papel);
            margin: 0;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid var(--verde-tenue);
        }
        .hero-q .prompt { color: var(--verde); margin-right: 0.5rem; font-weight: 700; }
        .hero-q .caret {
            display: inline-block;
            width: 0.62ch; height: 1.05em;
            background: var(--verde);
            margin-left: 0.18ch;
            transform: translateY(0.16em);
            box-shadow: 0 0 10px var(--verde);
            animation: blink 1.05s steps(1) infinite;
        }
        @keyframes blink { 50% { opacity: 0; } }
        @media (prefers-reduced-motion: reduce) {
            .hero-q .caret { animation: none; }
        }

        /* Tabs: mayúsculas finas, subrayado verde en el activo */
        button[data-baseweb="tab"] {
            font-family: 'IBM Plex Mono', monospace !important;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-size: 0.78rem;
        }
        button[data-baseweb="tab"][aria-selected="true"] { color: var(--verde) !important; }
        [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { background-color: var(--verde) !important; }

        /* Botones: contorno verde fósforo */
        .stButton > button, .stDownloadButton > button {
            font-family: 'IBM Plex Mono', monospace !important;
            border: 1px solid var(--verde) !important;
            color: var(--verde) !important;
            background: transparent !important;
            letter-spacing: 0.4px;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            background: var(--verde-tenue) !important;
            box-shadow: 0 0 14px var(--verde-tenue);
        }

        /* Foco accesible en verde */
        :focus-visible { outline: 2px solid var(--verde) !important; outline-offset: 2px; }

        /* Pestaña/sidebar: separador verde sutil */
        section[data-testid="stSidebar"] { border-right: 1px solid var(--verde-tenue); }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_estilo_terminal()

# --- Disclaimer fijo y visible ---------------------------------------
st.warning(f"⚠️ {export.DISCLAIMER}")

st.markdown(
    """
    <div class="hero">
      <div class="hero-eyebrow">Terminal de asociaciones · educativo</div>
      <h1 class="hero-q"><span class="prompt">&rsaquo;</span>¿Qué es lo que mueve el precio de este activo?<span class="caret"></span></h1>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Describe qué variables de contexto se movieron junto con los retornos de un activo. "
    "No predice ni recomienda."
)


# --- Cacheamos el análisis pesado por (ticker, opciones) -------------
@st.cache_data(show_spinner=False)
def _cached_analysis(ticker: str, include_macro: bool, run_xgb: bool) -> AssetResult:
    """Corre el pipeline y cachea el resultado (datos + modelado)."""
    return run_full_analysis(ticker, include_macro=include_macro, run_xgb=run_xgb)


@st.cache_data(show_spinner=False)
def _cached_summary(result_dict: dict) -> str:
    """Genera y cachea el resumen del LLM. La clave de cache es el dict del resultado."""
    from explanation.llm_explainer import generate_summary_from_dict

    return generate_summary_from_dict(result_dict)


# Cache de noticias con TTL corto (las noticias caducan rápido).
@st.cache_data(show_spinner=False, ttl=900)  # 15 minutos
def _cached_news(tickers: tuple[str, ...], por_ticker: int) -> list[dict]:
    """Trae noticias de cada ticker y las devuelve como dicts (para cachear).

    Es contexto cualitativo: NO se pasa al modelo ni al LLM.
    """
    from dataclasses import asdict

    from data_sources.news import YFinanceNewsSource

    fuente = YFinanceNewsSource()
    vistos: set[str] = set()
    salida: list[dict] = []
    for tk in tickers:
        try:
            for item in fuente.get_news(tk, limit=por_ticker):
                clave = item.url or item.titulo
                if clave in vistos:
                    continue
                vistos.add(clave)
                d = asdict(item)
                d["_consultado_por"] = tk  # de qué activo vino la búsqueda
                salida.append(d)
        except Exception:
            # Una fuente que falla no debe tumbar el panel de noticias.
            continue
    return salida


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_profile(ticker: str) -> dict:
    """Ficha descriptiva del activo (estilo finviz). Cacheada 1h."""
    from dataclasses import asdict

    from data_sources.profile import YFinanceProfileSource

    return asdict(YFinanceProfileSource().get_profile(ticker))


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_overview(ticker: str) -> dict:
    """Precios del activo + benchmark (SPY) y métricas de desempeño. Cacheada 1h."""
    from analysis.metrics import performance_metrics
    from data_sources.prices import YFinanceSource

    src = YFinanceSource()
    df = src.get_history(ticker, SETTINGS.start_date, SETTINGS.end_date)
    close = df["close"]
    try:
        bench = src.get_history("SPY", SETTINGS.start_date, SETTINGS.end_date)["close"]
    except Exception:
        bench = None

    # Guardamos OHLC (+volumen) para el gráfico de velas. Solo columnas presentes.
    ohlc: dict[str, list] = {}
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            ohlc[col] = [float(v) for v in df[col].values]
    return {
        "metrics": performance_metrics(close, bench),
        "fechas": [d.isoformat() for d in close.index],
        "ohlc": ohlc,
    }


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_ratios(ticker: str, market: dict) -> dict:
    """Ratios financieros descriptivos desde SEC EDGAR (5 categorías). Cacheada 1h.

    `market` (market_cap/precio de la ficha yfinance) entra como parámetro para que
    forme parte de la clave de caché y se use en los ratios de valuación.
    """
    from analysis.financial_ratios import compute_ratios
    from data_sources.fundamentals import SecEdgarSource

    facts = SecEdgarSource().get_facts(ticker)
    return compute_ratios(facts, market)


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_macro_panel(macro_weights: dict, start: str, end: str) -> list[dict]:
    """Panel macro: valores FRED actuales + pesos del modelo. Cacheada 1h."""
    from analysis.macro_panel import build_macro_panel
    from data_sources.macro import FredSource

    return build_macro_panel(macro_weights, FredSource(), start, end)


# --- Helpers de formato ----------------------------------------------
def _fmt_money(x: float | None) -> str:
    if x is None:
        return "—"
    for u, d in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(x) >= d:
            return f"${x / d:.2f}{u}"
    return f"${x:,.0f}"


def _fmt_pct(x: float | None, signo: bool = True) -> str:
    if x is None:
        return "—"
    return f"{x * 100:+.1f}%" if signo else f"{x * 100:.1f}%"


def _fmt_num(x: float | None, dec: int = 2) -> str:
    return "—" if x is None else f"{x:.{dec}f}"


def _estab_label(estab: float | None) -> str:
    """Estabilidad como etiqueta legible (alta/media/baja + valor)."""
    if estab is None:
        return "— (no seleccionada)"
    if estab >= 0.66:
        return f"alta ({estab:.2f})"
    if estab >= 0.33:
        return f"media ({estab:.2f})"
    return f"baja ({estab:.2f})"


def _google_translate_url(texto: str, tl: str = "es") -> str:
    """URL de Google Traductor que muestra `texto` traducido (origen autodetectado)."""
    from urllib.parse import quote

    return f"https://translate.google.com/?sl=auto&tl={tl}&op=translate&text={quote(texto)}"


def _render_ratios_financieros(ticker: str, perfil: dict | None) -> None:
    """Sección de ratios financieros (SEC EDGAR) en la pestaña Overview.

    Descriptivo: NO entra al modelo de retornos diarios. Degrada con gracia si falta
    la clave SEC_USER_AGENT o si la empresa no reporta a la SEC.
    """
    from analysis.financial_ratios import (
        _ETIQUETAS_CATEGORIA,
        format_ratio_value,
    )

    with st.expander("📑 Ratios financieros (SEC EDGAR · 5 categorías)", expanded=True):
        market = {
            "market_cap": (perfil or {}).get("market_cap"),
            "share_price": (perfil or {}).get("precio"),
        }
        try:
            with st.spinner("Calculando ratios desde SEC EDGAR..."):
                data = _cached_ratios(ticker, market)
        except Exception as exc:
            st.info(
                "No se pudieron calcular los ratios de SEC EDGAR "
                f"({type(exc).__name__}). Requiere `SEC_USER_AGENT` configurado y que el "
                "activo reporte a la SEC de EE.UU."
            )
            return

        as_of = data.get("as_of", {})
        st.caption(
            "Calculados de los estados contables que la empresa reporta a la SEC. "
            "**Son descriptivos, no entran al modelo ni son recomendación.** "
            f"Balance al {as_of.get('balance') or '—'} · "
            f"flujos **TTM** (últimos 12 meses) al {as_of.get('flujos_ttm') or '—'}. "
            "Los benchmarks (lectura) son referencias genéricas cross-industria: el "
            "software/tech suele correr márgenes y múltiplos más altos que el típico."
        )

        cats = data.get("categorias", {})
        # Dos columnas de categorías para aprovechar el ancho.
        orden = ["rentabilidad", "liquidez", "apalancamiento", "eficiencia", "valuacion"]
        cols = st.columns(2)
        for i, clave_cat in enumerate(orden):
            ratios = cats.get(clave_cat, {})
            filas = [
                {
                    "Ratio": r["nombre"],
                    "Valor": format_ratio_value(r["valor"], r["unidad"]),
                    "Lectura": r["interpretacion"],
                    "Fórmula": r["formula"],
                }
                for r in ratios.values()
            ]
            with cols[i % 2]:
                st.markdown(f"**{_ETIQUETAS_CATEGORIA.get(clave_cat, clave_cat)}**")
                st.dataframe(
                    pd.DataFrame(filas),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Ratio": st.column_config.TextColumn("Ratio", width="medium"),
                        "Valor": st.column_config.TextColumn("Valor", width="small"),
                        "Lectura": st.column_config.TextColumn("Lectura", width="medium"),
                        "Fórmula": st.column_config.TextColumn(
                            "Fórmula", width="medium",
                            help="Cómo se calcula el ratio.",
                        ),
                    },
                )

        faltantes = data.get("faltantes", [])
        if faltantes:
            st.caption(
                "Conceptos no hallados en los reportes (sus ratios quedan en '—'): "
                + ", ".join(faltantes)
            )
        st.caption(f"Fuente: {data.get('fuente', 'SEC EDGAR')}")


# Símbolos con bolsa para TradingView (los 7 activos objetivo cotizan en NASDAQ).
_TV_SYMBOLS = {
    "NVDA": "NASDAQ:NVDA", "GOOGL": "NASDAQ:GOOGL", "TSLA": "NASDAQ:TSLA",
    "MSFT": "NASDAQ:MSFT", "AAPL": "NASDAQ:AAPL", "AMZN": "NASDAQ:AMZN", "META": "NASDAQ:META",
}


def _tradingview_widget(ticker: str, height: int = 540) -> None:
    """Embebe el gráfico interactivo (Advanced Chart) de TradingView, tema oscuro.

    Es el widget público y gratuito de TradingView (vía iframe). Muestra velas,
    indicadores, dibujo, timeframes — la experiencia completa de su app. Requiere
    conexión a internet (carga desde tradingview.com).
    """
    symbol = _TV_SYMBOLS.get(ticker, ticker)
    html = f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%">
      <div id="tv_chart" style="height:{height - 24}px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{symbol}",
        "interval": "D",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "es",
        "toolbar_bg": "#0B0E11",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "hide_side_toolbar": false,
        "studies": ["MASimple@tv-basicstudies"],
        "container_id": "tv_chart"
      }});
      </script>
    </div>
    """
    components.html(html, height=height + 8)


# --- Barra lateral: selección y opciones -----------------------------
with st.sidebar:
    st.header("Configuración")
    ticker = st.selectbox("Activo objetivo", TICKERS_OBJETIVO)

    # Mostramos el grafo curado del activo elegido.
    rel = RELATIONSHIP_GRAPH.get(ticker, {})
    st.markdown("**Contexto curado (entra al modelo):**")
    st.markdown(f"- Competidores: {', '.join(rel.get('competidores', [])) or '—'}")
    st.markdown(f"- Proveedores: {', '.join(rel.get('proveedores', [])) or '—'}")
    st.markdown(f"- Contexto: {', '.join(rel.get('contexto', [])) or '—'}")
    st.markdown(f"- ETF sectorial: {rel.get('sector_etf', '—')}")

    # Conocimiento curado que NO entra al modelo (privadas / OTC ilíquido).
    no_listadas = entidades_no_listadas(ticker)
    if no_listadas:
        with st.expander(f"Relevantes que NO cotizan/líquidan en EE.UU. ({len(no_listadas)})"):
            st.caption(
                "No entran al modelo (sin precio usable), pero son contexto cualitativo."
            )
            for e in no_listadas:
                ref = f" · `{e['ticker_ref']}`" if e.get("ticker_ref") else ""
                st.markdown(f"- **{e['nombre']}** ({e['categoria']}) — {e['motivo']}{ref}")

    st.divider()
    include_macro = st.checkbox("Incluir variables macro (FRED)", value=True)
    run_xgb = st.checkbox("Incluir XGBoost + SHAP", value=True)
    metodo = st.radio("Método a graficar", ["lasso", "xgboost_shap"], index=0)

    st.divider()
    st.markdown("**Noticias (contexto cualitativo):**")
    mostrar_noticias = st.checkbox("Mostrar noticias", value=True)
    noticias_relacionadas = st.checkbox(
        "Incluir noticias de competidores/proveedores", value=False,
        help="Las noticias de las empresas relacionadas también pueden impactar al activo.",
    )

    analizar = st.button("🔍 Analizar", type="primary", use_container_width=True)


# --- Ejecución --------------------------------------------------------
if analizar:
    try:
        with st.spinner(f"Descargando datos y modelando {ticker}... (puede tardar)"):
            result = _cached_analysis(ticker, include_macro, run_xgb)
        st.session_state["_result_obj"] = result
        st.session_state["_ticker"] = ticker
    except Exception as exc:
        st.error(f"No se pudo completar el análisis: {exc}")
        st.stop()


# --- Mostrar resultados si existen -----------------------------------
result: AssetResult | None = st.session_state.get("_result_obj")

if result is None:
    st.info("Elegí un activo y tocá **Analizar** para comenzar.")
    st.stop()

st.subheader(f"Resultados para {result.ticker}")
st.caption(
    f"Período: {result.rango_fechas[0]} a {result.rango_fechas[1]} "
    f"· {result.n_observaciones} días de mercado."
)

tab_asoc, tab_over, tab_macro, tab_news = st.tabs(
    ["📊 Asociaciones", "🏢 Overview", "🌐 Macro", "📰 Noticias"]
)

# ===== Tab 1: Asociaciones (pesos + validación + resumen LLM) =========
with tab_asoc:
    col_chart, col_resumen = st.columns([1.2, 1])
    with col_chart:
        st.plotly_chart(charts.weights_bar_chart(result, metodo=metodo),
                        use_container_width=True)
        st.caption(
            "Verde = MISMO sentido que el activo · Rojo = sentido OPUESTO. "
            "La barra de error indica incertidumbre (a mayor barra, menos confiable)."
        )
        st.markdown("**Validación (out-of-sample vs baseline):**")
        for val in result.validaciones:
            estado = "✅ aporta" if val.aporta_sobre_baseline else "⚠️ no aporta"
            st.markdown(
                f"- `{val.modelo}`: {val.metrica} {val.error_modelo:.5f} vs "
                f"baseline {min(val.error_baseline_cero, val.error_baseline_rezago):.5f} "
                f"→ {estado} sobre el baseline."
            )

        with st.expander("ℹ️ Cómo interpretar esto (validación, pesos y normalización)"):
            st.markdown(
                """
**¿Qué dice la línea de validación?**

- **RMSE (error del modelo):** qué tan lejos quedan, en promedio, las predicciones
  del retorno real. Está en unidades de retorno diario y se mide **fuera de muestra**
  (en datos que el modelo no vio al entrenar). Más bajo = mejor.
- **baseline:** el error del "modelo bobo" de referencia (el mejor entre *predecir
  cero* y *repetir el retorno de ayer*).
- **✅ aporta:** el error del modelo es **menor** que el del baseline → las
  asociaciones que ves son una señal real, no ruido. Si dijera **⚠️ no aporta**, no
  habría que confiar en los pesos.

**¿Qué son los pesos?**

- `lasso` → relaciones **lineales**; el peso es el coeficiente (con signo).
- `xgboost_shap` → relaciones **no lineales**; el peso es la importancia |SHAP| media.
- **Estabilidad** = qué tan consistente es ese peso entre distintas ventanas de tiempo
  (1 = muy estable, 0 = inestable). La barra de error del gráfico es la incertidumbre.

**¿Los datos están normalizados?**

- **Lasso → SÍ.** Estandariza cada variable (media 0, desvío 1) antes de ajustar, para
  que la penalización sea justa y los coeficientes sean **comparables** entre sí.
- **XGBoost → NO, y está bien.** Los árboles parten por umbrales, así que son
  **invariantes a la escala**: estandarizar no cambiaría nada.
- **Antes de ambos modelos** los datos comparten preprocesamiento: retornos log,
  recorte de outliers (winsorización) y macro pasada a variación % (estacionariedad).
- El escalado del Lasso vive **dentro** del pipeline, así que en la validación se
  calcula solo con datos de entrenamiento → **sin fuga de información** (look-ahead).

> Nada de esto es predicción ni recomendación: describe **asociaciones históricas**.
                """
            )
    with col_resumen:
        st.markdown("### 📝 Resumen")
        try:
            with st.spinner("Generando resumen honesto (LLM)..."):
                resumen = _cached_summary(result.to_dict())
            st.write(resumen)
        except Exception as exc:
            resumen = ""
            st.error(f"No se pudo generar el resumen: {exc}")
        if resumen:
            md = export.to_markdown(result, resumen)
            st.download_button(
                "⬇️ Descargar resumen (Markdown)",
                data=md.encode("utf-8"),
                file_name=f"analisis_{result.ticker}.md",
                mime="text/markdown",
                use_container_width=True,
            )

# ===== Tab 2: Overview (ficha tipo finviz + desempeño) ===============
with tab_over:
    st.caption(
        "Datos descriptivos de referencia (fundamentals y desempeño histórico). "
        "No son señales del modelo ni recomendaciones."
    )
    try:
        with st.spinner("Cargando ficha del activo..."):
            perfil = _cached_profile(result.ticker)
            overview = _cached_overview(result.ticker)
    except Exception as exc:
        perfil, overview = None, None
        st.warning(f"No se pudo cargar el overview: {exc}")

    if perfil:
        nombre = perfil.get("nombre") or result.ticker
        st.markdown(
            f"#### {nombre}  ·  {perfil.get('sector') or '—'} / {perfil.get('industria') or '—'}"
        )
        c = st.columns(4)
        c[0].metric("Precio", _fmt_num(perfil.get("precio")))
        c[1].metric("Market cap", _fmt_money(perfil.get("market_cap")))
        c[2].metric("P/E (12m)", _fmt_num(perfil.get("pe_trailing")))
        c[3].metric("P/E proy.", _fmt_num(perfil.get("pe_forward")))
        c = st.columns(4)
        c[0].metric("Beta (informada)", _fmt_num(perfil.get("beta")))
        c[1].metric("Margen neto", _fmt_pct(perfil.get("margen_neto"), signo=False))
        c[2].metric("Dividend yield", _fmt_pct(perfil.get("dividend_yield"), signo=False))
        c[3].metric("Moneda", perfil.get("moneda") or "—")

    if overview:
        m = overview["metrics"]
        st.markdown("**Desempeño histórico (calculado de los precios):**")
        c = st.columns(5)
        c[0].metric("1 mes", _fmt_pct(m.get("retorno_1 mes")))
        c[1].metric("3 meses", _fmt_pct(m.get("retorno_3 meses")))
        c[2].metric("YTD", _fmt_pct(m.get("retorno_YTD")))
        c[3].metric("1 año", _fmt_pct(m.get("retorno_1 año")))
        c[4].metric("Dist. máx 52s", _fmt_pct(m.get("dist_max_52s")))
        c = st.columns(3)
        c[0].metric("Volatilidad anual", _fmt_pct(m.get("volatilidad_anual"), signo=False))
        c[1].metric("Máx drawdown", _fmt_pct(m.get("max_drawdown")))
        c[2].metric("Beta vs SPY", _fmt_num(m.get("beta")))

    # --- Ratios financieros (SEC EDGAR) — descriptivo, no entra al modelo ---
    _render_ratios_financieros(result.ticker, perfil)

    if overview:
        st.markdown("**Gráfico de precio**")
        fuente_grafico = st.radio(
            "Fuente del gráfico", ["Velas (local)", "TradingView"],
            horizontal=True, label_visibility="collapsed", key="fuente_grafico",
        )
        if fuente_grafico == "TradingView":
            _tradingview_widget(result.ticker)
            st.caption(
                "Gráfico interactivo de **TradingView** (velas, indicadores, dibujo, "
                "timeframes). Podés cambiar el símbolo y agregar estudios. Requiere internet."
            )
        else:
            idx = pd.to_datetime(overview["fechas"])
            ohlc_df = pd.DataFrame(overview.get("ohlc", {}), index=idx)
            st.plotly_chart(
                charts.price_candlestick_chart(
                    ohlc_df, result.ticker, m.get("max_52s"), m.get("min_52s")
                ),
                use_container_width=True,
            )
            st.caption("Velas diarias · verde = cierre ≥ apertura, rojo = cierre < apertura. "
                       "Usá los botones 1M/6M/YTD/1A/TODO para acercar.")

# ===== Tab 3: Macro (valores FRED + peso del modelo) =================
with tab_macro:
    st.caption(
        "Valor actual de cada variable macro y el peso/sentido que el modelo le asignó "
        "sobre este activo. Lenguaje de asociación: NO es predicción ni recomendación."
    )
    from analysis.macro_panel import extract_macro_weights

    macro_weights = extract_macro_weights(result)
    try:
        with st.spinner("Cargando datos macro..."):
            filas = _cached_macro_panel(
                macro_weights, result.rango_fechas[0], result.rango_fechas[1]
            )
    except Exception as exc:
        filas = []
        st.warning(f"No se pudo cargar el panel macro: {exc}")

    if not filas:
        st.info(
            "Sin datos macro disponibles. Verificá `FRED_API_KEY`, o el análisis se "
            "corrió sin macro (desmarcá esa opción)."
        )
    else:
        tabla = []
        for f in filas:
            if not f["en_modelo"]:
                asociacion = "— (no seleccionada)"
            else:
                asociacion = ("📈 mismo sentido" if f["signo"] == "+"
                              else "📉 sentido opuesto")
            tabla.append({
                "Variable": f["nombre"],
                "Qué es": glosa_por_nombre(f["nombre"]) or "—",
                "Valor": _fmt_num(f["valor"], 2),
                "Variación": (_fmt_pct(f["variacion_pct"])
                              if f["variacion_pct"] is not None else "—"),
                "Asociación con el activo": asociacion,
                "Estabilidad": _estab_label(f["estabilidad"]),
            })
        st.dataframe(
            pd.DataFrame(tabla),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Variable": st.column_config.TextColumn("Variable", width="medium"),
                "Qué es": st.column_config.TextColumn(
                    "Qué es", width="large",
                    help="Explicación breve de qué mide la variable y por qué importa."),
                "Valor": st.column_config.TextColumn(
                    "Valor", help="Último valor publicado (nivel real de la serie)."),
                "Variación": st.column_config.TextColumn(
                    "Variación", help="Cambio respecto del dato anterior de la serie."),
                "Asociación con el activo": st.column_config.TextColumn(
                    "Asociación con el activo", width="medium",
                    help="Cómo tendió a moverse el activo cuando esta variable subía: "
                         "mismo sentido (📈) u opuesto (📉). Es asociación histórica, "
                         "no una causa ni una predicción."),
                "Estabilidad": st.column_config.TextColumn(
                    "Estabilidad", width="medium",
                    help="Qué tan CONSISTENTE fue esa asociación entre distintas ventanas "
                         "de tiempo: 1 = muy estable/confiable, 0 = muy inestable. "
                         "“— (no seleccionada)” = el modelo no le dio peso (Lasso la "
                         "descartó por aportar poco)."),
            },
        )
        st.caption(
            "👉 La columna **Qué es** explica cada variable; pasá el mouse sobre el ícono "
            "ⓘ de cada encabezado para más detalle. **Estabilidad** = qué tan consistente "
            "fue la asociación entre ventanas de tiempo (vacío = el modelo no la seleccionó)."
        )

# ===== Tab 4: Noticias (contexto cualitativo, fuera del modelo) ======
with tab_news:
    if not mostrar_noticias:
        st.info("Activá **Mostrar noticias** en la barra lateral para verlas.")
    else:
        st.caption(
            "Trasfondo cualitativo que **podría** ser relevante. NO entra al modelo ni se "
            "usa para afirmar causalidad: el precio y las noticias se muestran por separado."
        )
        traducir = st.checkbox(
            "🌐 Traducir titulares al español (Google Traductor)",
            help="Los titulares suelen venir en inglés. Al activarlo, cada título abre su "
                 "traducción en Google Traductor; el enlace a la fuente original queda al lado.",
        )
        tickers_news: tuple[str, ...] = (result.ticker,)
        por_ticker = 8
        if noticias_relacionadas:
            relacionados = [t for t in all_feature_tickers(result.ticker)
                            if t != RELATIONSHIP_GRAPH.get(result.ticker, {}).get("sector_etf")]
            # Acotamos a 8 fuentes y menos titulares c/u: si no, son demasiadas llamadas
            # a yfinance y el panel parece colgado.
            relacionados = relacionados[:8]
            tickers_news = (result.ticker, *relacionados)
            por_ticker = 5
            st.caption(f"Consultando {len(tickers_news)} fuentes: {', '.join(tickers_news)}")
        try:
            with st.spinner(f"Buscando noticias en {len(tickers_news)} fuente(s)… "
                            f"(puede tardar unos segundos)"):
                noticias = _cached_news(tickers_news, por_ticker=por_ticker)
        except Exception as exc:
            noticias = []
            st.warning(f"No se pudieron cargar las noticias: {exc}")

        if not noticias:
            st.info(
                "No hay noticias recientes disponibles. Yahoo/yfinance a veces no "
                "devuelve titulares; probá de nuevo en un momento."
            )
        else:
            st.caption(f"Mostrando {min(len(noticias), 30)} de {len(noticias)} titulares.")
            for n in noticias[:30]:
                origen = n.get("_consultado_por", "")
                etiqueta = f" · _vía {origen}_" if origen and origen != result.ticker else ""
                meta = " · ".join(p for p in [n.get("fuente", ""), n.get("publicado", "")] if p)
                titulo = n.get("titulo", "(sin título)")
                url = n.get("url", "")
                if traducir:
                    # El título abre su traducción; la fuente original queda al lado.
                    encabezado = f"**[{titulo}]({_google_translate_url(titulo)})**"
                    fuente_link = f" · [fuente original]({url})" if url else ""
                else:
                    encabezado = f"**[{titulo}]({url})**" if url else f"**{titulo}**"
                    fuente_link = ""
                st.markdown(f"{encabezado}{etiqueta}{fuente_link}")
                if meta:
                    st.caption(meta)

st.divider()
st.caption(f"⚠️ {export.DISCLAIMER}")
