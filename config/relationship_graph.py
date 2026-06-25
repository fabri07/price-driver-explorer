"""
Grafo de relaciones entre activos — DATO CURADO A MANO.
=======================================================

★★★ ESTE ES EL ACTIVO MÁS VALIOSO DEL PROYECTO ★★★

Este archivo NO se genera automáticamente. Es conocimiento de dominio curado a mano:
para cada activo objetivo definimos qué otros activos consideramos "contexto"
relevante (competidores, proveedores, pares sectoriales y un ETF del sector).

El modelo va a medir con qué variables se movieron juntos los retornos del activo,
pero la *selección* de candidatos vive acá. Un grafo bien armado es la diferencia
entre un análisis útil y ruido. Editalo a mano con criterio.

DOS NIVELES (importante)
------------------------
1. `RELATIONSHIP_GRAPH`  → entidades que SÍ alimentan el modelo de retornos diarios.
   Solo tickers con cotización LÍQUIDA en EE.UU. (NYSE/NASDAQ o ADRs negociables).
   yfinance los resuelve directamente y tienen retorno diario confiable.

2. `ENTIDADES_NO_LISTADAS` → conocimiento curado que NO entra al modelo, porque:
   - son EMPRESAS PRIVADAS (no cotizan: Cerebras, Groq, OpenAI, Anthropic, Waymo…), o
   - cotizan solo como OTC pink-sheet MUY ILÍQUIDO o en bolsas extranjeras sin ADR
     usable (Samsung, SK Hynix, Foxconn, CATL, LG Energy Solution…).
   Meter precios rancios/ilíquidos a un modelo de retornos diarios genera retornos
   falsos y correlaciones espurias, así que los documentamos aparte. Quedan
   disponibles para la capa de explicación o un análisis cualitativo futuro, pero
   NO se descargan ni se modelan.

Reglas de edición
-----------------
- En `RELATIONSHIP_GRAPH` usá SOLO tickers que coticen líquido en EE.UU.
- ADRs OTC (sufijo aclarado con comentario, p.ej. BYDDY/PCRFY/VWAGY) son aceptables
  pero tienen menos volumen: si preferís solo cotizaciones primarias, quitalos.
- `competidores`: compiten por el mismo mercado.
- `proveedores`: aguas arriba en la cadena (insumos, fabricación, equipos).
- `contexto`: pares grandes / clientes / nombres correlacionados.
- `sector_etf`: un ETF que represente al sector.

MATERIALES ESTRATÉGICOS (tierras raras, litio, metales)
-------------------------------------------------------
Las tierras raras (neodimio, disprosio, praseodimio) son CRUCIALES: alimentan los
imanes permanentes NdFeB de los motores eléctricos y se usan en electrónica avanzada.
China domina ~70% de la minería y ~85-90% del PROCESAMIENTO, así que su precio/oferta
es un riesgo geopolítico real. Pero NO hay una serie de precios limpia y gratis en
FRED. Por eso las modelamos por el canal de ACCIONES (mejor señal diaria que un índice
mensual rancio):
  - REMX → ETF VanEck de tierras raras y metales estratégicos (mineras + procesadoras).
  - MP   → MP Materials, principal minera/procesadora de tierras raras de EE.UU.
  - ALB  → Albemarle, litio (ya en proveedores de TSLA).
Los precios de cobre, níquel, aluminio, hierro y uranio sí están en FRED (IMF) y entran
por el canal MACRO (config/fred_series.py). El litio NO está gratis en FRED → vía ALB.

Para agregar un activo objetivo nuevo:
1. Agregá su ticker a `TICKERS_OBJETIVO`.
2. Agregá una entrada en `RELATIONSHIP_GRAPH` con las cuatro claves.
3. (Opcional) Documentá sus entidades privadas/ilíquidas en `ENTIDADES_NO_LISTADAS`.
"""

from __future__ import annotations

# Activos para los que la herramienta produce un análisis.
# El selector de la UI se arma a partir de esta lista.
TICKERS_OBJETIVO: list[str] = ["NVDA", "GOOGL", "TSLA", "MSFT", "AAPL", "AMZN", "META"]


# =====================================================================
# NIVEL 1 — Entidades que SÍ alimentan el modelo (cotización líquida US).
# =====================================================================
RELATIONSHIP_GRAPH: dict[str, dict[str, list[str] | str]] = {
    # NVIDIA — diseño de GPUs / aceleradores de IA (fabless).
    "NVDA": {
        "competidores": [
            "AMD",    # aceleradores de IA (Instinct MI300/MI400)
            "INTC",   # Gaudi + fundiciones; rival en cómputo
        ],
        "proveedores": [
            "TSM",    # ★ TSMC: fabrica TODOS los chips avanzados (cuello de botella crítico)
            "ASML",   # litografía EUV que TSMC necesita para imprimir los chips
            "MU",     # Micron: memoria HBM de alto ancho de banda para GPUs de IA
        ],
        "contexto": [
            "MSFT",   # hyperscaler: gran comprador de GPUs (también diseña Maia)
            "AMZN",   # AWS: gran comprador (también diseña Trainium)
            "META",   # gran comprador de GPUs para entrenamiento
            "GOOGL",  # cliente cloud (también diseña TPUs → comprador y rival a la vez)
            "REMX",   # ETF tierras raras/metales estratégicos: proxy de riesgo de
                      # suministro (China domina el procesamiento) que afecta a los semis
        ],
        "sector_etf": "SMH",  # VanEck Semiconductor ETF
    },
    # Alphabet (Google) — buscador, publicidad, cloud, IA.
    "GOOGL": {
        "competidores": [
            "MSFT",   # nube (Azure), productividad, IA (Copilot)
            "META",   # publicidad digital, IA open-source (Llama)
            "AMZN",   # nube (AWS), publicidad
            "AAPL",   # iOS vs Android, hardware de consumo
        ],
        "proveedores": [
            "NVDA",   # GPUs de IA para Google Cloud
            "AVGO",   # Broadcom: co-diseña/provee componentes de las TPU
            "TSM",    # fabrica los Tensor (Pixel) y chips TPU
            "INTC",   # acuerdo de manufactura de custom silicon de IA para datacenters
        ],
        "contexto": [],  # rivales privados (OpenAI/Anthropic) y socios PE → ver ENTIDADES_NO_LISTADAS
        "sector_etf": "XLC",  # Communication Services Select Sector
    },
    # Tesla — vehículos eléctricos, baterías y autonomía.
    "TSLA": {
        "competidores": [
            "GM",      # automotriz tradicional en transición EV
            "F",       # automotriz tradicional en transición EV
            "RIVN",    # EV nativo (camionetas/SUV premium)
            "LCID",    # Lucid: EV premium
            "NIO",     # ADR (NYSE): EV chino con software avanzado
            "LI",      # Li Auto, ADR (NASDAQ): EV/EREV chino
            "BYDDY",   # BYD, ADR OTC: rival nº1 global en EV+híbridos (OTC: menos volumen)
            "VWAGY",   # Volkswagen, ADR OTC: mayor automotriz legacy en transición EV
        ],
        "proveedores": [
            "ON",      # onsemi: semiconductores de potencia
            "ALB",     # Albemarle: litio (insumo nº1 de baterías)
            "STM",     # STMicroelectronics: semis de potencia / control de motores
            "TXN",     # Texas Instruments: chips analógicos / gestión de energía
            "PCRFY",   # Panasonic, ADR OTC: socio histórico de celdas (Gigafactory NV)
            "MP",      # MP Materials: imanes de tierras raras (NdFeB) para motores EV
        ],
        "contexto": [
            "REMX",    # ETF tierras raras/metales estratégicos: neodimio/disprosio de
                       # los imanes permanentes + litio/níquel de baterías (proxy de
                       # costo de insumos y riesgo geopolítico de suministro)
        ],
        "sector_etf": "XLY",  # Consumer Discretionary Select Sector
    },
    # Microsoft — nube (Azure), software/productividad e IA; gaming.
    "MSFT": {
        "competidores": [
            "AMZN",   # AWS: rival nº1 en infraestructura cloud corporativa
            "GOOGL",  # Google Cloud + Workspace (rival en nube y productividad)
            "CRM",    # Salesforce (dueño de Slack): SaaS empresarial + colaboración
            "ZM",     # Zoom: comunicación/videollamadas vs Teams
            "META",   # rival en modelos de IA open-source (Llama vs MSFT/OpenAI)
            "SONY",   # PlayStation: rival en consolas (ADR NYSE líquido)
        ],
        "proveedores": [
            "NVDA",   # ★ proveedor crítico de GPUs de IA para Azure
            "AMD",    # GPUs/CPUs alternativos para datacenters
            "TSM",    # fabrica los chips (de NVIDIA/AMD y los custom Maia/Cobalt)
            "INTC",   # CPUs de servidor x86 para la flota Azure
        ],
        "contexto": [
            "AAPL",   # par mega-cap tech; correlación de complejo (no compite de frente)
        ],
        "sector_etf": "XLK",  # Technology Select Sector (MSFT es top holding)
    },
    # Apple — hardware integrado verticalmente (iPhone/Mac), servicios y silicio propio.
    "AAPL": {
        "competidores": [
            "GOOGL",  # Android vs iOS; servicios y publicidad
            "AMZN",   # servicios/streaming/nube y hardware de hogar (Echo)
            "NFLX",   # streaming vs Apple TV+
            "SPOT",   # Spotify: música vs Apple Music
            "HPQ",    # HP: PCs vs Mac
            "DELL",   # Dell: PCs vs Mac
        ],
        "proveedores": [
            "TSM",    # ★ único capaz de fabricar los chips serie M (Mac) y A (iPhone)
            "QCOM",   # módems 5G del iPhone (cliente clave, en transición a módem propio)
            "AVGO",   # Broadcom: RF/wireless/filtros del iPhone
            "SWKS",   # Skyworks: front-end de RF (alta concentración en Apple)
            "QRVO",   # Qorvo: front-end de RF (alta concentración en Apple)
            "CRUS",   # Cirrus Logic: chips de audio casi-dedicados a Apple (proxy puro)
            "SONY",   # sensores de cámara del iPhone (proveedor exclusivo, ADR líquido)
            "LPL",    # LG Display: paneles OLED para iPhone (ADR NYSE)
        ],
        "contexto": [
            "MSFT",   # par mega-cap tech; correlación de complejo
        ],
        "sector_etf": "XLK",  # Technology Select Sector (AAPL es top holding)
    },
    # Amazon — e-commerce/logística + nube (AWS); cadenas de suministro distintas.
    "AMZN": {
        "competidores": [
            "WMT",    # Walmart: rival global en retail/e-commerce
            "SHOP",   # Shopify: infraestructura de e-commerce
            "MSFT",   # Azure: rival nº1 de AWS en cloud
            "GOOGL",  # Google Cloud (GCP)
            "ORCL",   # Oracle Cloud (OCI)
            "PDD",    # PDD Holdings (Temu): e-commerce chino de bajo costo (ADR NASDAQ)
        ],
        "proveedores": [
            "NVDA",   # GPUs de IA para AWS (que además diseña Trainium/Inferentia)
            "AVGO",   # Broadcom: co-diseño de silicio/red customizada
            "MRVL",   # Marvell: acuerdo multi-generación de silicio custom y óptica para AWS
            "ANET",   # Arista: switching Ethernet de alta gama en datacenters
            "VRT",    # Vertiv: energía y refrigeración líquida de servidores de IA
            "TSM",    # fabrica los chips custom (Graviton/Trainium) y de NVIDIA
            "UPS",    # paquetería para tramos de distribución complejos
            "FDX",    # FedEx: paquetería/logística
        ],
        "contexto": [
            "AAPL",   # par mega-cap tech
            "META",   # par mega-cap; ciclo de gasto en IA/datacenters correlacionado
        ],
        "sector_etf": "XLY",  # Consumer Discretionary Select Sector (AMZN es top holding)
    },
    # Meta — publicidad/atención (apps), IA (Llama/MTIA) y hardware XR (Quest/Ray-Ban).
    "META": {
        "competidores": [
            "GOOGL",  # YouTube + publicidad digital (duopolio de ads)
            "SNAP",   # Snapchat: atención y publicidad
            "AAPL",   # Vision Pro (XR) y política de privacidad (ATT) que pega al ad-targeting
            "PINS",   # Pinterest: atención y presupuesto publicitario
            "RDDT",   # Reddit: atención y publicidad social
        ],
        "proveedores": [
            "NVDA",   # ★ uno de los mayores compradores del mundo (H100/H200/Blackwell)
            "QCOM",   # acuerdo multi-generación: CPU de datacenter "Dragonfly C1000" + SoCs de Quest
            "AVGO",   # Broadcom: co-diseño multi-generación del acelerador custom MTIA
            "TSM",    # fabrica las GPUs/MTIA físicamente
            "ARM",    # arquitectura de los CPUs custom de servidor
        ],
        "contexto": [
            "MSFT",   # par mega-cap; ciclo de gasto en IA correlacionado
            "AMZN",   # par mega-cap tech
        ],
        "sector_etf": "XLC",  # Communication Services Select Sector (META es top holding)
    },
}


# =====================================================================
# NIVEL 2 — Conocimiento curado que NO entra al modelo.
# =====================================================================
# Empresas privadas o con cotización US no usable (OTC ilíquido / sin ADR).
# Estructura por activo: lista de dicts {nombre, categoria, motivo, ticker_ref}.
#   - `ticker_ref` es solo informativo (NO se descarga): el ticker OTC/extranjero
#     existe pero no es apto para un modelo de retornos diarios.
# NO lo consume `all_feature_tickers`; sirve para mostrar contexto cualitativo.
ENTIDADES_NO_LISTADAS: dict[str, list[dict[str, str]]] = {
    "NVDA": [
        # Proveedores extranjeros / OTC ilíquido
        {"nombre": "Samsung Electronics", "categoria": "proveedor",
         "motivo": "OTC pink-sheet ilíquido / bolsa de Corea", "ticker_ref": "SSNLF / 005930.KS"},
        {"nombre": "SK Hynix", "categoria": "proveedor",
         "motivo": "OTC ilíquido / bolsa de Corea", "ticker_ref": "HXSCL / 000660.KS"},
        {"nombre": "Foxconn (Hon Hai)", "categoria": "proveedor",
         "motivo": "OTC ilíquido / bolsa de Taiwán", "ticker_ref": "HNHPF / 2317.TW"},
        {"nombre": "Wistron", "categoria": "proveedor",
         "motivo": "bolsa de Taiwán, sin ADR usable", "ticker_ref": "3231.TW"},
        # Competidores privados (no cotizan)
        {"nombre": "Cerebras Systems", "categoria": "competidor",
         "motivo": "empresa privada", "ticker_ref": ""},
        {"nombre": "Groq", "categoria": "competidor",
         "motivo": "empresa privada (LPUs de inferencia)", "ticker_ref": ""},
        {"nombre": "SambaNova Systems", "categoria": "competidor",
         "motivo": "empresa privada", "ticker_ref": ""},
        {"nombre": "Tenstorrent", "categoria": "competidor",
         "motivo": "empresa privada", "ticker_ref": ""},
    ],
    "GOOGL": [
        {"nombre": "OpenAI", "categoria": "competidor",
         "motivo": "empresa privada (ChatGPT/SearchGPT)", "ticker_ref": ""},
        {"nombre": "Anthropic", "categoria": "competidor",
         "motivo": "empresa privada (Claude); Google tiene participación", "ticker_ref": ""},
        {"nombre": "Blackstone (infraestructura IA)", "categoria": "socio/contexto",
         "motivo": "BX cotiza pero como socio PE de datacenters su retorno no traza a GOOGL",
         "ticker_ref": "BX"},
    ],
    "TSLA": [
        {"nombre": "Waymo", "categoria": "competidor",
         "motivo": "subsidiaria de Alphabet (sin ticker propio); líder en robotaxis",
         "ticker_ref": "vía GOOGL"},
        {"nombre": "CATL", "categoria": "proveedor",
         "motivo": "baterías LFP; bolsa de Shenzhen/HK, sin ADR US usable", "ticker_ref": "300750.SZ"},
        {"nombre": "LG Energy Solution", "categoria": "proveedor",
         "motivo": "baterías; bolsa de Corea, sin ADR usable", "ticker_ref": "373220.KS"},
        {"nombre": "Xiaomi", "categoria": "competidor",
         "motivo": "EV chino; OTC ilíquido / bolsa de HK", "ticker_ref": "XIACY / 1810.HK"},
        {"nombre": "Hyundai", "categoria": "competidor",
         "motivo": "OTC ilíquido / bolsa de Corea", "ticker_ref": "HYMTF / 005380.KS"},
        {"nombre": "Lynas Rare Earths", "categoria": "proveedor (materiales estratégicos)",
         "motivo": "mayor procesador de tierras raras fuera de China; ASX/OTC ilíquido. "
                   "Exposición líquida a tierras raras → vía REMX/MP", "ticker_ref": "LYSCF / LYC.AX"},
        {"nombre": "Procesamiento de tierras raras en China", "categoria": "riesgo de suministro",
         "motivo": "~85-90% del refinado mundial de tierras raras; sin ticker. Riesgo "
                   "geopolítico de los imanes NdFeB. Proxy modelable → REMX", "ticker_ref": "vía REMX"},
    ],
    "MSFT": [
        {"nombre": "OpenAI", "categoria": "socio/competidor",
         "motivo": "empresa privada; MSFT es su mayor inversor pero su retorno no traza a MSFT",
         "ticker_ref": ""},
        {"nombre": "Anthropic", "categoria": "competidor",
         "motivo": "empresa privada (Claude); rival en modelos de IA", "ticker_ref": ""},
        {"nombre": "Nintendo", "categoria": "competidor",
         "motivo": "consolas; ADR OTC ilíquido / bolsa de Tokio", "ticker_ref": "NTDOY / 7974.T"},
        {"nombre": "Tencent", "categoria": "competidor",
         "motivo": "gaming/cloud chino; ADR OTC / bolsa de Hong Kong", "ticker_ref": "TCEHY / 0700.HK"},
        {"nombre": "Quanta Computer", "categoria": "proveedor",
         "motivo": "ODM de servidores Azure; bolsa de Taiwán, sin ADR usable", "ticker_ref": "2382.TW"},
        {"nombre": "Wiwynn", "categoria": "proveedor",
         "motivo": "ODM de servidores de datacenter; bolsa de Taiwán", "ticker_ref": "6669.TW"},
        {"nombre": "Foxconn (Hon Hai)", "categoria": "proveedor",
         "motivo": "ensamblaje de servidores; OTC ilíquido / bolsa de Taiwán", "ticker_ref": "HNHPF / 2317.TW"},
    ],
    "AAPL": [
        {"nombre": "Samsung Electronics", "categoria": "competidor/proveedor",
         "motivo": "rival en smartphones Y principal proveedor de paneles OLED (Samsung Display); "
                   "OTC pink ilíquido / bolsa de Corea", "ticker_ref": "SSNLF / 005930.KS"},
        {"nombre": "Xiaomi", "categoria": "competidor",
         "motivo": "smartphones; OTC ilíquido / bolsa de Hong Kong", "ticker_ref": "XIACY / 1810.HK"},
        {"nombre": "Huawei", "categoria": "competidor",
         "motivo": "empresa privada (no cotiza); smartphones resurgentes en China", "ticker_ref": ""},
        {"nombre": "Oppo / Vivo", "categoria": "competidor",
         "motivo": "privadas (grupo BBK Electronics); smartphones de bajo/medio costo", "ticker_ref": ""},
        {"nombre": "Lenovo", "categoria": "competidor",
         "motivo": "PCs; ADR OTC / bolsa de Hong Kong", "ticker_ref": "LNVGY / 0992.HK"},
        {"nombre": "Foxconn (Hon Hai)", "categoria": "proveedor",
         "motivo": "ensamblador nº1 del iPhone; OTC ilíquido / bolsa de Taiwán", "ticker_ref": "HNHPF / 2317.TW"},
        {"nombre": "Pegatron", "categoria": "proveedor",
         "motivo": "ensamblaje del iPhone; bolsa de Taiwán, sin ADR usable", "ticker_ref": "4938.TW"},
        {"nombre": "BOE Technology", "categoria": "proveedor",
         "motivo": "paneles para iPhone; bolsa de Shenzhen, sin ADR usable", "ticker_ref": "000725.SZ"},
        {"nombre": "Lingyi iTech", "categoria": "proveedor",
         "motivo": "componentes mecánicos/módulos internos; bolsa de Shenzhen", "ticker_ref": "002600.SZ"},
    ],
    "AMZN": [
        {"nombre": "Shein", "categoria": "competidor",
         "motivo": "empresa privada; e-commerce de moda de bajo costo", "ticker_ref": ""},
        {"nombre": "DHL (Deutsche Post)", "categoria": "proveedor",
         "motivo": "mensajería para tramos complejos; ADR OTC / bolsa de Frankfurt", "ticker_ref": "DHLGY / DHL.DE"},
    ],
    "META": [
        {"nombre": "TikTok (ByteDance)", "categoria": "competidor",
         "motivo": "empresa privada china; rival nº1 por la atención de usuarios jóvenes", "ticker_ref": ""},
        {"nombre": "X (Twitter)", "categoria": "competidor",
         "motivo": "empresa privada; red social/atención", "ticker_ref": ""},
        {"nombre": "EssilorLuxottica", "categoria": "proveedor/socio",
         "motivo": "fabrica los armazones/cristales de las gafas Ray-Ban Meta; ADR OTC / Euronext París",
         "ticker_ref": "ESLOY / EL.PA"},
        {"nombre": "HTC", "categoria": "competidor",
         "motivo": "VR (Vive); bolsa de Taiwán, sin ADR usable", "ticker_ref": "2498.TW"},
    ],
}


# =====================================================================
# Descripciones legibles por ticker (para tooltips / UI educativa).
# Una línea por activo: qué es y por qué aparece como contexto.
# =====================================================================
DESCRIPCIONES_TICKER: dict[str, str] = {
    # Semis / tech
    "AMD": "Advanced Micro Devices — rival en CPUs/GPUs y aceleradores de IA.",
    "INTC": "Intel — chips y fundiciones; rival y a la vez posible fabricante.",
    "TSM": "TSMC — fabrica los chips avanzados del mundo; cuello de botella crítico.",
    "ASML": "ASML — única fuente de litografía EUV para chips de punta.",
    "MU": "Micron — memoria HBM de alto ancho de banda para GPUs de IA.",
    "MSFT": "Microsoft — nube Azure e IA (Copilot); gran comprador de GPUs.",
    "AMZN": "Amazon — nube AWS y publicidad; gran comprador de chips.",
    "META": "Meta — publicidad digital e IA; gran comprador de GPUs.",
    "GOOGL": "Alphabet (Google) — buscador, publicidad, nube y TPUs.",
    "AAPL": "Apple — hardware de consumo e iOS.",
    "AVGO": "Broadcom — co-diseña chips de IA y de redes.",
    "NVDA": "NVIDIA — líder en GPUs/aceleradores de IA.",
    "QCOM": "Qualcomm — módems de smartphone y, ahora, CPUs de datacenter (Dragonfly).",
    "MRVL": "Marvell — silicio custom y óptica para datacenters (socio de AWS/Azure).",
    "ANET": "Arista Networks — switching Ethernet de alta gama para datacenters de IA.",
    "VRT": "Vertiv — energía y refrigeración líquida para servidores de IA.",
    "SWKS": "Skyworks — front-end de RF; altísima concentración de ingresos en Apple.",
    "QRVO": "Qorvo — front-end de RF para smartphones (proveedor de Apple).",
    "CRUS": "Cirrus Logic — chips de audio casi-dedicados a Apple (proxy puro del iPhone).",
    "LPL": "LG Display — paneles OLED para iPhone (ADR NYSE).",
    "ARM": "Arm Holdings — arquitectura de CPU que licencian Apple, Meta, etc. (ADR).",
    # Big Tech / software / plataformas
    "CRM": "Salesforce — CRM/SaaS empresarial; dueño de Slack.",
    "ZM": "Zoom — videollamadas y comunicación (rival de Teams).",
    "ORCL": "Oracle — software empresarial y nube (OCI).",
    "SHOP": "Shopify — infraestructura de e-commerce para comercios.",
    "WMT": "Walmart — mayor retailer global; rival de e-commerce de Amazon.",
    "PDD": "PDD Holdings — e-commerce chino (Temu/Pinduoduo), ADR NASDAQ.",
    "NFLX": "Netflix — streaming de video (rival de Apple TV+/Prime Video).",
    "SPOT": "Spotify — streaming de música (rival de Apple Music).",
    "SNAP": "Snap — Snapchat; atención y publicidad social.",
    "PINS": "Pinterest — descubrimiento visual; publicidad social.",
    "RDDT": "Reddit — foros/comunidades; atención y publicidad.",
    "SONY": "Sony — PlayStation y sensores de cámara (proveedor exclusivo del iPhone), ADR NYSE.",
    "HPQ": "HP Inc. — PCs e impresión (rival de Mac).",
    "DELL": "Dell Technologies — PCs y servidores empresariales.",
    "UPS": "UPS — paquetería/logística (proveedor de envíos de Amazon).",
    "FDX": "FedEx — paquetería/logística (proveedor de envíos de Amazon).",
    # Autos / EV
    "GM": "General Motors — automotriz tradicional en transición a EV.",
    "F": "Ford — automotriz tradicional en transición a EV.",
    "RIVN": "Rivian — fabricante EV (camionetas/SUV premium).",
    "LCID": "Lucid — EV premium.",
    "NIO": "NIO — EV chino con software avanzado (ADR).",
    "LI": "Li Auto — EV/EREV chino (ADR).",
    "BYDDY": "BYD — líder global en EV+híbridos (ADR OTC).",
    "VWAGY": "Volkswagen — mayor automotriz legacy en transición EV (ADR OTC).",
    # Proveedores EV / materiales
    "ON": "onsemi — semiconductores de potencia para EV.",
    "ALB": "Albemarle — productor de litio, insumo nº1 de baterías.",
    "STM": "STMicroelectronics — semis de potencia y control de motores.",
    "TXN": "Texas Instruments — chips analógicos y gestión de energía.",
    "PCRFY": "Panasonic — socio histórico de celdas de batería (ADR OTC).",
    "MP": "MP Materials — minera/procesadora de tierras raras de EE.UU. (imanes NdFeB).",
    "REMX": "ETF de tierras raras y metales estratégicos; proxy de riesgo de suministro (China domina el procesamiento).",
    # ETFs sectoriales
    "SMH": "ETF de semiconductores (VanEck) — el sector chip completo.",
    "XLK": "ETF de tecnología (Technology Select Sector) — software, hardware y semis grandes.",
    "XLC": "ETF de servicios de comunicación (Google, Meta, telecom…).",
    "XLY": "ETF de consumo discrecional (autos, retail, lujo…).",
}


def descripcion_ticker(ticker: str) -> str:
    """Descripción legible de un ticker (vacío si no está documentado)."""
    return DESCRIPCIONES_TICKER.get(ticker, "")


def all_feature_tickers(target: str) -> list[str]:
    """Devuelve la lista de tickers a descargar como *features* para `target`.

    Une competidores + proveedores + contexto + el ETF sectorial, deduplica y
    EXCLUYE al propio activo objetivo (su retorno es el target, no un feature).
    NO incluye `ENTIDADES_NO_LISTADAS` (esas no tienen precio usable).

    Lanza KeyError si el target no está en el grafo (error explícito a propósito:
    significa que falta curar ese activo).
    """
    if target not in RELATIONSHIP_GRAPH:
        raise KeyError(
            f"'{target}' no está en RELATIONSHIP_GRAPH. "
            f"Agregalo a mano en config/relationship_graph.py antes de analizarlo."
        )

    rel = RELATIONSHIP_GRAPH[target]
    tickers: list[str] = []
    tickers += list(rel.get("competidores", []))  # type: ignore[arg-type]
    tickers += list(rel.get("proveedores", []))   # type: ignore[arg-type]
    tickers += list(rel.get("contexto", []))      # type: ignore[arg-type]

    etf = rel.get("sector_etf")
    if isinstance(etf, str) and etf:
        tickers.append(etf)

    # Deduplicar preservando orden y sacar el target si apareciera por error.
    seen: set[str] = set()
    out: list[str] = []
    for t in tickers:
        if t and t != target and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def feature_role(target: str, ticker: str) -> str:
    """Etiqueta legible del rol de `ticker` respecto de `target`.

    Sirve para mostrar en la UI y en el resumen ("competidor", "proveedor", etc.).
    """
    rel = RELATIONSHIP_GRAPH.get(target, {})
    if ticker in rel.get("competidores", []):      # type: ignore[operator]
        return "competidor"
    if ticker in rel.get("proveedores", []):        # type: ignore[operator]
        return "proveedor"
    if ticker in rel.get("contexto", []):           # type: ignore[operator]
        return "contexto"
    if ticker == rel.get("sector_etf"):
        return "ETF sectorial"
    return "otro"


def entidades_no_listadas(target: str) -> list[dict[str, str]]:
    """Entidades curadas que NO entran al modelo (privadas / OTC ilíquido / extranjeras).

    Devuelve la lista documental para `target` (vacía si no hay). Útil para la capa
    de explicación o una vista cualitativa; NO se descarga ni se modela.
    """
    return ENTIDADES_NO_LISTADAS.get(target, [])
