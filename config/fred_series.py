"""
Catálogo de series macro de FRED + metadatos anti look-ahead y estacionariedad.
===============================================================================

FRED entrega cada observación fechada por su *período de referencia* (ej. el CPI de
marzo lleva fecha de marzo), pero ese dato recién se *publica* semanas después. Si
alineáramos el CPI de marzo al 1 de marzo en una serie diaria, estaríamos usando
información del futuro: look-ahead bias.

Para evitarlo, cada serie de baja frecuencia lleva un `publication_lag_days`: cuántos
días, de forma conservadora, tardó en estar disponible. El pipeline desplaza la serie
ese lag ANTES de forward-fillearla al calendario diario. Ver pipeline/macro_align.py.

ESTACIONARIEDAD (campo `transformacion`)
----------------------------------------
Muchas series son *niveles con tendencia* (CPI, PBI, nóminas, producción, precios de
commodities): crecen sostenidamente en el tiempo. Como el precio de un activo también
sube, una regresión cruda puede encontrar correlaciones ESPURIAS por co-tendencia. Por
eso cada serie declara cómo volverse (aprox.) estacionaria antes de modelar:

- "nivel" : ya es estacionaria (tasas, spreads, VIX, sentimiento acotado, desempleo).
- "yoy"   : variación interanual (%). Quita la tendencia de largo plazo. Para índices
            de precios y niveles que crecen con la economía (inflación, PBI, empleo,
            precios de commodities mensuales).
- "mom"   : variación período-a-período (%). Para series de mercado DIARIAS que
            interesan por su co-movimiento diario (dólar, petróleo, gas).

La transformación se aplica en pipeline/macro_align.py, sobre la frecuencia nativa,
antes del lag y del forward-fill. OJO: afecta solo lo que ve el MODELO; el panel Macro
de la UI sigue mostrando el *nivel* actual (más legible para el usuario).

CANAL DE CONDICIONES FINANCIERAS (tasas reales, breakeven, crédito)
-------------------------------------------------------------------
Para acciones de CRECIMIENTO (tech/IA/EV) el driver macro dominante no suele ser el
dato "duro" (CPI, empleo) sino el canal financiero: la TASA REAL a 10 años (DFII10,
canal de la tasa de descuento), la INFLACIÓN ESPERADA de mercado (T10YIE breakeven) y
los SPREADS DE CRÉDITO (BAMLH0A0HYM2 high-yield, BAMLC0A0CM grado de inversión) que
miden el apetito de riesgo en tiempo real. Todos son diarios (o el NFCI semanal),
acotados/mean-reverting → entran como "nivel", sin riesgo de co-tendencia. Es la
contraparte de mercado, de alta frecuencia, de los indicadores macro mensuales.

Notas
-----
- Las series diarias de tasas/VIX tienen lag ~1 (se conocen al cierre).
- Los lags son aproximaciones conservadoras (mejor sobreestimar el retraso).
- PMI/ISM Manufacturero y de Servicios NO está gratis en FRED (licencia de copyright).
  Proxies de actividad: Producción Industrial (INDPRO) y Ventas Minoristas (RSAFS).
- Tierras raras, litio, oro/plata spot: NO hay serie limpia y gratis en FRED. Las
  tierras raras y el litio se cubren por el canal de ACCIONES (REMX, MP, ALB) en
  config/relationship_graph.py — un ETF/acción líquido da mejor señal diaria que un
  índice mensual rancio. Ver la nota "MATERIALES ESTRATÉGICOS" en ese archivo.
- OCDE: los indicadores líderes (CLI, confianza empresarial) se traen por el mirror
  OFICIAL de OCDE en FRED (mismo dato, vivo, sin un source SDMX frágil aparte). Si en
  el futuro se quiere sourcing directo, la arquitectura desacoplada permite agregar un
  `OecdSource` que implemente MacroDataSource sin tocar el resto.
- Banco Mundial: datos ANUALES (PBI, comercio, pobreza). NO entran a este modelo diario
  (una serie anual forward-filleada a diario reintroduce co-tendencia espuria). Quedan
  para un panel descriptivo de contexto global (no modelado). `WorldBankSource` ya está
  implementado en data_sources/macro.py por si se arma ese panel.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FredSeriesSpec:
    """Especificación de una serie macro de FRED."""

    series_id: str          # ID en FRED (ej. "CPIAUCSL")
    nombre: str             # nombre legible para la UI / resumen
    freq: str               # "diaria" | "semanal" | "mensual" | "trimestral"
    publication_lag_days: int  # retraso conservador entre período de ref. y publicación
    transformacion: str = "nivel"  # "nivel" | "yoy" | "mom" (estacionariedad)


# Catálogo de series macro. Agregá/quitá libremente (cada una: id FRED, nombre,
# frecuencia, lag de publicación conservador, transformación de estacionariedad).
FRED_SERIES: list[FredSeriesSpec] = [
    # ====== DIARIAS — TASAS Y CURVA (ya estacionarias → nivel) =========
    FredSeriesSpec("DFF",     "Tasa de fondos federales (efectiva)", "diaria", 1, "nivel"),
    FredSeriesSpec("DGS3MO",  "Letra del Tesoro a 3 meses (tasa de mercado monetario)", "diaria", 1, "nivel"),
    FredSeriesSpec("DGS2",    "Rendimiento del Tesoro a 2 años (sensible a la Fed)", "diaria", 1, "nivel"),
    FredSeriesSpec("DGS10",   "Rendimiento del Tesoro a 10 años", "diaria", 1, "nivel"),
    FredSeriesSpec("T10Y2Y",  "Spread de la curva (10 años – 2 años)", "diaria", 1, "nivel"),
    FredSeriesSpec("T10Y3M",  "Spread de la curva (10 años – 3 meses) — señal de recesión preferida de la Fed", "diaria", 1, "nivel"),

    # ====== DIARIAS — TASA REAL E INFLACIÓN ESPERADA (nivel) ==========
    # Canal de la tasa de DESCUENTO: la valuación de las acciones de crecimiento (tech)
    # es muy sensible a la tasa real. El breakeven es la inflación que descuenta el
    # mercado (no la realizada del CPI). Ambas series de TIPS son diarias → nivel.
    FredSeriesSpec("DFII10",  "Tasa real del Tesoro a 10 años (TIPS, ajustado por inflación)", "diaria", 1, "nivel"),
    FredSeriesSpec("T10YIE",  "Inflación esperada a 10 años (breakeven de mercado)", "diaria", 1, "nivel"),

    # ====== CONDICIONES FINANCIERAS / CRÉDITO (nivel) =================
    # Apetito de riesgo: los spreads de crédito se ENSANCHAN cuando el mercado teme
    # (risk-off) y se comprimen en risk-on. Suelen ser el driver macro dominante de las
    # acciones de crecimiento, más que el dato macro "duro". Spreads diarios → nivel;
    # el NFCI es un índice semanal centrado en 0 (mean-reverting) → nivel.
    FredSeriesSpec("BAMLH0A0HYM2", "Spread de bonos high-yield (riesgo de crédito basura) — apetito de riesgo", "diaria", 1, "nivel"),
    FredSeriesSpec("BAMLC0A0CM",   "Spread de bonos corporativos grado de inversión (IG)", "diaria", 1, "nivel"),
    FredSeriesSpec("NFCI",         "Índice de condiciones financieras (Fed de Chicago) — laxas vs. restrictivas", "semanal", 7, "nivel"),

    # --- Riesgo (nivel) y divisa (mom: interesa el cambio diario) ---
    FredSeriesSpec("VIXCLS",  "Índice de volatilidad VIX", "diaria", 1, "nivel"),
    FredSeriesSpec("DTWEXBGS", "Índice del dólar (amplio, ponderado por comercio)", "diaria", 1, "mom"),
    # --- Energía (precios diarios → variación diaria) ---
    FredSeriesSpec("DCOILWTICO", "Precio del petróleo WTI (crudo)", "diaria", 1, "mom"),
    FredSeriesSpec("DHHNGSP", "Precio del gas natural (Henry Hub)", "diaria", 1, "mom"),

    # ====== MENSUALES — PRECIOS / INFLACIÓN (niveles → yoy) ============
    # CPI del mes M se publica ~mediados de M+1. 45 días conservador.
    FredSeriesSpec("CPIAUCSL", "Inflación: índice de precios al consumidor (CPI)", "mensual", 45, "yoy"),
    # Core CPI (excl. alimentos y energía) — el favorito de los bancos centrales.
    FredSeriesSpec("CPILFESL", "Inflación núcleo: CPI excl. alimentos y energía", "mensual", 45, "yoy"),
    # IPP / PPI (inflación mayorista, anticipa la del consumidor).
    FredSeriesSpec("PPIFIS",  "Inflación mayorista: precios al productor (PPI, demanda final)", "mensual", 30, "yoy"),

    # ====== EMPLEO ====================================================
    # Tasa de desempleo: ya es una tasa acotada → nivel.
    FredSeriesSpec("UNRATE",  "Tasa de desempleo", "mensual", 35, "nivel"),
    # Nómina no agrícola (NFP): nivel de empleo que crece → variación interanual.
    FredSeriesSpec("PAYEMS",  "Empleo no agrícola — NFP (crecimiento interanual)", "mensual", 35, "yoy"),
    # Solicitudes iniciales de desempleo (semanal): variación interanual.
    FredSeriesSpec("ICSA",    "Solicitudes iniciales de desempleo (semanal)", "semanal", 7, "yoy"),

    # ====== ACTIVIDAD / CONSUMO / SENTIMIENTO =========================
    FredSeriesSpec("INDPRO",  "Producción industrial (proxy de actividad/PMI)", "mensual", 30, "yoy"),
    FredSeriesSpec("RSAFS",   "Ventas minoristas (consumo privado)", "mensual", 30, "yoy"),
    # Sentimiento acotado (índice mean-reverting) → nivel.
    FredSeriesSpec("UMCSENT", "Confianza del consumidor (U. de Michigan)", "mensual", 30, "nivel"),

    # ====== INDICADORES LÍDERES — OCDE (vía mirror oficial en FRED) ====
    # OCDE produce estos indicadores; FRED los espeja. Mensuales, vivos a 2026-05.
    # Son LÍDERES (anticipan el ciclo), a diferencia de los demás que son coincidentes
    # o rezagados. El CLI oscila alrededor de 100 y la confianza alrededor de 0 → ya son
    # estacionarios (nivel; aplicar % sería un error). Lag ~40 días (release ~mediados
    # del mes siguiente, con revisiones). Nota: las variantes de confianza del CONSUMIDOR
    # de OCDE en FRED están discontinuadas (ene-2024); esa señal la da UMCSENT (Michigan).
    FredSeriesSpec("USALOLITOAASTSAM", "OCDE — Indicador líder compuesto (CLI) EE.UU.", "mensual", 40, "nivel"),
    FredSeriesSpec("BSCICP02USM460S",  "OCDE — Confianza empresarial EE.UU. (BCI)", "mensual", 40, "nivel"),

    # ====== SECTOR EXTERNO ============================================
    # Balanza comercial: flujo (puede ser negativo); el % de un negativo confunde el
    # signo, así que la dejamos en nivel.
    FredSeriesSpec("BOPGSTB", "Balanza comercial (bienes y servicios)", "mensual", 45, "nivel"),

    # ====== PBI (nivel que crece → yoy) ===============================
    FredSeriesSpec("GDP",     "Producto Bruto Interno (PBI)", "trimestral", 30, "yoy"),

    # ====== COMMODITIES — METALES / MINERALES (IMF, mensual → yoy) ====
    # Precios globales del IMF (Primary Commodity Prices). Insumos de hardware y EV,
    # y termómetro de la demanda industrial global. Publicación ~inicio del mes M+1;
    # 35 días conservador.
    FredSeriesSpec("PCOPPUSDM",   "Cobre (precio global) — termómetro industrial", "mensual", 35, "yoy"),
    FredSeriesSpec("PALUMUSDM",   "Aluminio (precio global) — carrocerías/empaque EV", "mensual", 35, "yoy"),
    FredSeriesSpec("PNICKUSDM",   "Níquel (precio global) — cátodos de baterías EV", "mensual", 35, "yoy"),
    FredSeriesSpec("PIORECRUSDM", "Mineral de hierro (precio global) — acero/industria", "mensual", 35, "yoy"),
    FredSeriesSpec("PURANUSDM",   "Uranio (precio global) — energía nuclear / datacenters IA", "mensual", 35, "yoy"),
    FredSeriesSpec("PMETAINDEXM", "Índice de metales industriales (IMF)", "mensual", 35, "yoy"),

    # ====== COMMODITIES — AGRÍCOLAS (IMF, mensual → yoy) ===============
    # Contexto macro / inflación de alimentos. Vínculo DIRECTO débil con tech/EV
    # (probablemente Lasso los pode), pero son parte del cuadro macro de commodities.
    FredSeriesSpec("PFANDBINDEXM", "Índice de alimentos y bebidas (IMF)", "mensual", 35, "yoy"),
    FredSeriesSpec("PMAIZMTUSDM",  "Maíz (precio global)", "mensual", 35, "yoy"),
    FredSeriesSpec("PWHEAMTUSDM",  "Trigo (precio global)", "mensual", 35, "yoy"),
    FredSeriesSpec("PSOYBUSDM",    "Soja (precio global)", "mensual", 35, "yoy"),
]


# Glosario legible por serie (qué mide / por qué importa), para tooltips y UI educativa.
GLOSARIO: dict[str, str] = {
    "DFF": "Tasa de referencia de la Fed. Más alta → crédito más caro, presiona a las acciones de crecimiento.",
    "DGS3MO": "Letra del Tesoro a 3 meses; tasa de mercado monetario, el extremo corto de la curva.",
    "DGS2": "Rendimiento del Tesoro a 2 años; refleja expectativas de la Fed a corto plazo.",
    "DGS10": "Rendimiento del Tesoro a 10 años; tasa de descuento de referencia para valuar acciones.",
    "T10Y2Y": "Pendiente de la curva (10a − 2a). Negativa = señal clásica de recesión.",
    "T10Y3M": "Pendiente de la curva (10a − 3m); la versión que la Fed de NY usa en su modelo de recesión.",
    "DFII10": "Tasa real a 10 años (TIPS). Sube → más presión sobre las acciones de crecimiento (tech).",
    "T10YIE": "Inflación que el mercado descuenta a 10 años (breakeven = nominal − real); expectativa, no dato realizado.",
    "BAMLH0A0HYM2": "Sobretasa de los bonos basura sobre el Tesoro. Se ensancha en pánico (risk-off); termómetro del apetito de riesgo.",
    "BAMLC0A0CM": "Sobretasa de los bonos corporativos de buena calidad (grado de inversión) sobre el Tesoro.",
    "NFCI": "Índice de la Fed de Chicago: >0 condiciones financieras restrictivas, <0 laxas. Resume crédito, liquidez y apalancamiento.",
    "VIXCLS": "Índice del 'miedo': volatilidad esperada del S&P 500. Sube en pánico de mercado.",
    "DTWEXBGS": "Fortaleza del dólar frente a una canasta de socios comerciales.",
    "DCOILWTICO": "Precio del crudo WTI; costo de energía y termómetro de la economía global.",
    "DHHNGSP": "Precio del gas natural (Henry Hub); costo de energía en EE.UU.",
    "CPIAUCSL": "Inflación al consumidor (todos los rubros). Más alta → Fed más dura.",
    "CPILFESL": "Inflación núcleo (sin alimentos ni energía); la que más mira la Fed.",
    "PPIFIS": "Inflación mayorista (precios al productor); suele anticipar la del consumidor.",
    "UNRATE": "Tasa de desempleo. Baja = economía fuerte; muy baja puede presionar salarios.",
    "PAYEMS": "Crecimiento del empleo no agrícola (NFP); pulso del mercado laboral.",
    "ICSA": "Nuevos pedidos de seguro de desempleo por semana; detecta giros rápidos del empleo.",
    "INDPRO": "Producción de fábricas y minas; proxy de actividad industrial (sustituto del PMI).",
    "RSAFS": "Ventas minoristas; pulso del consumo privado, motor de la economía de EE.UU.",
    "UMCSENT": "Confianza del consumidor (U. de Michigan); ánimo para gastar.",
    "BOPGSTB": "Balanza comercial (exportaciones − importaciones) de bienes y servicios.",
    "GDP": "Producto Bruto Interno; el tamaño total de la economía de EE.UU.",
    "PCOPPUSDM": "Precio global del cobre; 'Dr. Copper', termómetro de la demanda industrial.",
    "PALUMUSDM": "Precio global del aluminio; insumo de carrocerías y empaques.",
    "PNICKUSDM": "Precio global del níquel; clave en cátodos de baterías de EV.",
    "PIORECRUSDM": "Precio global del mineral de hierro; insumo del acero y la construcción.",
    "PURANUSDM": "Precio global del uranio; combustible nuclear, demanda creciente por datacenters de IA.",
    "PMETAINDEXM": "Índice de metales industriales; canasta agregada de la demanda metálica.",
    "PFANDBINDEXM": "Índice global de precios de alimentos y bebidas; inflación de alimentos.",
    "PMAIZMTUSDM": "Precio global del maíz.",
    "PWHEAMTUSDM": "Precio global del trigo.",
    "PSOYBUSDM": "Precio global de la soja; sensible al comercio EE.UU.–China.",
    "USALOLITOAASTSAM": "Indicador líder compuesto de la OCDE; anticipa giros del ciclo ~6-9 meses.",
    "BSCICP02USM460S": "Confianza empresarial de la OCDE; expectativas de las empresas.",
}


def glosa_por_nombre(nombre: str) -> str:
    """Glosa legible de una serie macro por su nombre de display (vacío si no es macro)."""
    for s in FRED_SERIES:
        if s.nombre == nombre:
            return GLOSARIO.get(s.series_id, "")
    return ""


def series_ids() -> list[str]:
    """IDs de todas las series configuradas."""
    return [s.series_id for s in FRED_SERIES]


def spec_by_id(series_id: str) -> FredSeriesSpec:
    """Devuelve la spec de una serie por su ID (KeyError si no existe)."""
    for s in FRED_SERIES:
        if s.series_id == series_id:
            return s
    raise KeyError(f"Serie FRED '{series_id}' no está en FRED_SERIES.")
