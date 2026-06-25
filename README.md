# Asociaciones de precio — herramienta educativa

Herramienta **educativa** que **explica** (no predice) qué variables de contexto
—competidores, proveedores, ETF sectorial y macro— se movieron junto con los
retornos de un activo. Calcula pesos interpretables con su estabilidad y genera un
resumen en lenguaje natural, honesto sobre la incertidumbre.

> ⚠️ **No es asesoramiento de inversión.** Describe asociaciones históricas, no
> predicciones, y no da recomendaciones de compra/venta.

---

## ¿Qué hace?

Para un activo (NVDA, GOOGL, TSLA por defecto):

1. Descarga precios del activo y de su contexto curado, más macro de FRED.
2. Calcula qué variables se asociaron a sus retornos log diarios, con peso, signo y
   estabilidad, usando **dos métodos**: Lasso (lineal, interpretable) y XGBoost+SHAP
   (no lineal).
3. Valida **out-of-sample** contra baselines naive y reporta si el modelo aporta.
4. Genera un resumen en español con un LLM, fuertemente acotado a lenguaje de
   asociación.
5. Lo muestra en una interfaz web con gráfico de pesos y descarga en Markdown.

---

## Estructura

```
config/         # grafo de relaciones (curado a mano), series FRED, settings
data_sources/   # interfaces abstractas + YFinance (precios/noticias/ficha) / FRED / WorldBank / SEC EDGAR
pipeline/        # retornos, anti look-ahead, alineación, ensamblado del dataset
modeling/        # Lasso, XGBoost+SHAP, validación OOS, estabilidad, orquestador
explanation/    # system prompt acotado + llamada a la API de Anthropic
analysis/        # métricas de desempeño + panel macro (para los paneles de la UI)
app/             # interfaz Streamlit (tabs), gráficos plotly, exportación
run_analysis.py # orquestador CLI (end-to-end sin UI)
```

La interfaz Streamlit tiene **cuatro pestañas**:
- **📊 Asociaciones** — pesos del modelo (Lasso / XGBoost+SHAP), validación OOS y el resumen del LLM (descargable).
- **🏢 Overview** — ficha tipo *finviz* (sector, market cap, P/E, beta, márgenes), desempeño calculado de los precios (retornos por ventana, volatilidad, drawdown, beta vs S&P 500, rango de 52 semanas) y **ratios financieros desde SEC EDGAR** en 5 categorías (rentabilidad, liquidez, apalancamiento, eficiencia, valuación), con lectura cualitativa y fecha del dato.
- **🌐 Macro** — valor actual de cada serie FRED + el peso/sentido/estabilidad que el modelo le asignó al activo (lenguaje de asociación).
- **📰 Noticias** — titulares recientes (contexto cualitativo).

Overview y Macro son **descriptivos**: no son señales del modelo ni recomendaciones.

El **grafo de relaciones** (`config/relationship_graph.py`) es el dato curado a mano
y el activo más valioso del proyecto. Tiene **dos niveles**:

- `RELATIONSHIP_GRAPH`: entidades con cotización **líquida en EE.UU.** (NYSE/NASDAQ o
  ADRs negociables) que **sí alimentan** el modelo de retornos diarios.
- `ENTIDADES_NO_LISTADAS`: conocimiento curado de actores **privados** (Cerebras,
  Groq, OpenAI, Anthropic, Waymo…) o de cotización **no usable** (OTC ilíquido /
  bolsas extranjeras sin ADR: Samsung, SK Hynix, Foxconn, CATL, LG Energy…). NO
  entran al modelo (un precio rancio genera retornos falsos), pero quedan
  documentados y se muestran en la UI como contexto cualitativo.

Editá ambos para ajustar el contexto de cada activo.

### Arquitectura: fuentes desacopladas

El pipeline y la UI dependen solo de interfaces abstractas
(`PriceDataSource`, `MacroDataSource`, `FundamentalsSource`). Para cambiar de
proveedor (ej. yfinance → Polygon) se crea una clase nueva que implemente la
interfaz y se inyecta en `run_analysis.run_full_analysis` — sin tocar nada más.

---

## Instalación

Requiere **Python 3.11+**.

```bash
pip install -r requirements.txt
cp .env.example .env   # luego completá las claves (ver abajo)
```

### Claves y configuración

| Variable            | ¿Requerida?                     | Cómo obtenerla |
|---------------------|---------------------------------|----------------|
| `FRED_API_KEY`      | Sí, para variables macro        | Gratis en https://fredaccount.stlouisfed.org/apikeys |
| `ANTHROPIC_API_KEY` | Sí, para el resumen del LLM     | https://console.anthropic.com/ (API Keys) |
| `SEC_USER_AGENT`    | Sí, para fundamentals (SEC)     | Texto propio: `"Nombre Apellido tu_email@dominio.com"` |

- **yfinance** y **World Bank** no requieren clave.
- **SEC EDGAR** exige un `User-Agent` con email de contacto; sin él la SEC devuelve 403.
- Si falta una clave requerida, el sistema **falla explícito** con un mensaje claro
  (no degrada silenciosamente).

---

## Uso

### CLI (validación end-to-end)

```bash
python run_analysis.py NVDA
python run_analysis.py GOOGL --sin-resumen   # sin llamar al LLM
python run_analysis.py TSLA --sin-xgb        # solo Lasso (más rápido)
python run_analysis.py NVDA --sin-macro      # sin variables FRED
python run_analysis.py NVDA --noticias       # + noticias recientes
```

Imprime los pesos por variable (signo + estabilidad), el reporte de validación
OOS vs baseline y el resumen del LLM.

### Interfaz web

```bash
streamlit run app/streamlit_app.py
```

Elegí un activo, tocá **Analizar**, mirá el gráfico de pesos y el resumen, y
descargá el resultado en Markdown.

---

## Notas importantes

- **yfinance es para desarrollo / investigación / validación. NO tiene licencia para
  uso comercial.** Para producción comercial, migrá a un proveedor con licencia
  (Polygon, EODHD, etc.) creando otra clase `PriceDataSource`.
- **Anti look-ahead bias:** las series macro de baja frecuencia (CPI, GDP) se
  alinean al calendario diario SOLO a partir de su fecha real de publicación (con un
  lag conservador por serie en `config/fred_series.py`). Ver `pipeline/macro_align.py`.
- **Estacionariedad:** muchas series macro son *niveles con tendencia* (CPI, PBI,
  nóminas, producción, precios de commodities). Contra un retorno diario eso genera
  correlaciones espurias por co-tendencia. Por eso cada serie declara una
  `transformacion` en `config/fred_series.py`: `nivel` (ya estacionaria: tasas, VIX,
  desempleo), `yoy` (variación interanual: inflación, PBI, empleo, commodities
  mensuales) o `mom` (variación diaria: dólar, petróleo, gas). El modelo usa la serie
  transformada; el panel Macro de la UI sigue mostrando el *nivel* legible.
- **Normalización / escalado:** depende del modelo.
  - **Lasso → SÍ estandariza** (`StandardScaler`: media 0, desvío 1) dentro de su
    pipeline. La penalización L1 es sensible a la escala, así que estandarizar la hace
    justa y vuelve los coeficientes comparables entre sí (por eso se leen como "pesos").
  - **XGBoost → NO**, a propósito: los árboles parten por umbrales y son invariantes a
    la escala; estandarizar no cambiaría nada. Los valores SHAP ya salen en unidades del
    retorno, comparables sin escalar la entrada.
  - **Antes de ambos** los datos comparten preprocesamiento (retornos log,
    winsorización de outliers, macro en variación %), así que llegan en escalas
    parecidas; el `StandardScaler` del Lasso es el ajuste fino final.
  - El escalado vive **dentro** del pipeline → en la validación se ajusta solo con el
    tramo de entrenamiento de cada ventana, sin fuga de información (look-ahead).
- **Condiciones financieras (canal de mercado):** además del macro "duro" (CPI, empleo,
  PBI), el catálogo incluye el canal de alta frecuencia que suele dominar a las acciones
  de crecimiento: tasa real a 10 años (`DFII10`), inflación esperada de mercado
  (`T10YIE` breakeven), spreads de crédito high-yield e investment-grade
  (`BAMLH0A0HYM2`, `BAMLC0A0CM`), curva 10a−3m (`T10Y3M`), letra a 3 meses (`DGS3MO`) y
  el índice de condiciones financieras de la Fed de Chicago (`NFCI`). Son series diarias
  (o semanales) acotadas → entran como `nivel`, sin co-tendencia espuria.
- **Commodities y materiales estratégicos:** el canal macro incluye metales y minerales
  (cobre, aluminio, níquel, hierro, uranio, índice de metales) y agrícolas (maíz, trigo,
  soja, índice de alimentos) — precios globales del IMF vía FRED. Las **tierras raras** y
  el **litio** NO tienen serie limpia y gratis en FRED, así que se cubren por el canal de
  acciones (`REMX`, `MP`, `ALB` en `config/relationship_graph.py`): un ETF/acción líquido
  da mejor señal diaria que un índice mensual rancio.
- **Fundamentals (SEC EDGAR):** se usan SOLO en la capa **descriptiva** (pestaña
  Overview), nunca en el modelo de retornos diarios (son trimestrales/anuales y no
  encajan en esa frecuencia; mezclarlos reintroduciría co-tendencia). El módulo
  `analysis/financial_ratios.py` extrae los conceptos US-GAAP de companyfacts (con
  listas de fallback para tolerar migraciones de tag entre filings) y calcula las 5
  categorías de ratios del framework de análisis financiero. Valida completitud: si un
  concepto no aparece, el ratio queda en '—' (no inventa un 0). Requiere `SEC_USER_AGENT`;
  sin esa clave, la sección degrada con un mensaje claro.
- **Honestidad:** el resumen del LLM está acotado por un system prompt visible
  (`explanation/prompts.py`) que prohíbe lenguaje causal/predictivo y obliga a marcar
  la incertidumbre.
- **Canal de noticias (`data_sources/news.py`):** trae titulares recientes vía
  yfinance (sin clave) como **contexto cualitativo**. Es deliberadamente **separado**
  del modelo y del prompt del LLM: las noticias NO alimentan los pesos ni se usan para
  afirmar causalidad. En la UI hay un panel "Noticias recientes" (con opción de incluir
  noticias de competidores/proveedores); en CLI, `--noticias`. Misma fuente abstracta
  (`NewsDataSource`) que el resto: para producción con licencia, se cambia la clase.

---

## Verificación

1. `python run_analysis.py NVDA` → descarga datos reales, imprime pesos + validación
   + resumen. Repetir con GOOGL y TSLA.
2. `streamlit run app/streamlit_app.py` → gráfico, resumen, descarga, disclaimer.
3. Sin `FRED_API_KEY` → al usar macro, error claro (no degradación silenciosa).

---

## Licencia

Código bajo licencia [MIT](LICENSE) — usalo, modificalo y compartilo libremente.

> **Sobre los datos:** la licencia MIT cubre **este código**, no los datos de
> terceros. `yfinance`/Yahoo es para uso de investigación/desarrollo (sin licencia
> comercial); FRED, SEC EDGAR y World Bank tienen sus propios términos. Para uso
> comercial, migrá a un proveedor de precios con licencia (ver la nota en *Notas
> importantes*).

Proyecto **educativo**: describe asociaciones históricas, no es asesoramiento de
inversión ni hace predicciones.
