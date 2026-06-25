"""
Ratios financieros descriptivos a partir de SEC EDGAR (companyfacts XBRL).
=========================================================================

Calcula las 5 categorías de ratios del framework de análisis financiero —
RENTABILIDAD, LIQUIDEZ, APALANCAMIENTO, EFICIENCIA y VALUACIÓN— a partir de los
estados contables que la empresa reporta a la SEC.

★ ESTO ES DESCRIPTIVO, NO ENTRA AL MODELO ★
Los fundamentals son trimestrales/anuales y NO se mezclan con el modelo de retornos
DIARIOS (eso reintroduciría co-tendencia espuria; ver pipeline/macro_align.py). Este
módulo alimenta SOLO la pestaña Overview como contexto cualitativo de referencia. No
es señal del modelo ni recomendación de inversión.

Crédito: fórmulas, categorías y rangos de benchmark adaptados del skill
`financial-analyst` (scripts/ratio_calculator.py, references/financial-ratios-guide.md).
Se "vendorizan" acá a propósito: el skill vive fuera del repo, y el proyecto depende
solo de sus propios módulos (mismo criterio de desacople que data_sources/base.py).

Disciplina de datos (principio del skill: validar completitud antes de calcular)
--------------------------------------------------------------------------------
- Flujos (ingresos, costo, resultado, flujo de caja): se toma el último EJERCICIO
  ANUAL reportado (duración ~365 días), por robustez entre fiscales no calendario.
- Stocks de balance (activos, pasivos, patrimonio, caja…): el último valor INSTANTÁNEO
  reportado (puede ser de un 10-Q más reciente que el último 10-K).
- Si un concepto no aparece, el ratio queda en None (interpretación "datos
  insuficientes"); NUNCA se inventa un 0 que se leería como un ratio real.
- Cada categoría informa su fecha "as-of" para que el usuario sepa de cuándo es el dato.

⚠️ Los benchmarks son referencias GENÉRICAS cross-industria. El software/tech suele
correr márgenes y múltiplos más altos que el típico; leer la lectura como orientación,
no como veredicto.
"""

from __future__ import annotations

from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Mapeo de conceptos US-GAAP (listas de fallback: el primer tag con dato gana).
# Los emisores no siempre usan el mismo tag; por eso varios candidatos por línea.
# ---------------------------------------------------------------------------
_REVENUE = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]
_COGS = ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"]
_OPERATING_INCOME = ["OperatingIncomeLoss"]
_NET_INCOME = ["NetIncomeLoss", "ProfitLoss"]
_INTEREST_EXPENSE = [
    "InterestExpense",
    "InterestExpenseDebt",
    "InterestAndDebtExpense",
    "InterestExpenseNonoperating",
]
_DEP_AMORT = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
]
_OPERATING_CASH_FLOW = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]

_ASSETS = ["Assets"]
_CURRENT_ASSETS = ["AssetsCurrent"]
_LIABILITIES = ["Liabilities"]
_CURRENT_LIABILITIES = ["LiabilitiesCurrent"]
_EQUITY = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
_CASH = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]
_INVENTORY = ["InventoryNet"]
_RECEIVABLES = ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"]
_LT_DEBT_NONCURRENT = ["LongTermDebtNoncurrent", "LongTermDebt"]
_LT_DEBT_CURRENT = ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"]
_SHARES = ["EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"]

# Benchmarks genéricos cross-industria: (bajo, típico, alto). Del skill financial-analyst.
_BENCHMARKS: dict[str, tuple[float, float, float]] = {
    "roe": (0.08, 0.15, 0.25),
    "roa": (0.03, 0.06, 0.12),
    "margen_bruto": (0.25, 0.40, 0.60),
    "margen_operativo": (0.05, 0.15, 0.25),
    "margen_neto": (0.03, 0.10, 0.20),
    "ratio_corriente": (1.0, 1.5, 3.0),
    "ratio_rapido": (0.8, 1.0, 2.0),
    "ratio_caja": (0.2, 0.5, 1.0),
    "deuda_patrimonio": (0.3, 0.8, 2.0),
    "cobertura_intereses": (2.0, 5.0, 10.0),
    "dscr": (1.0, 1.5, 2.5),
    "rotacion_activos": (0.5, 1.0, 2.0),
    "rotacion_inventario": (4.0, 8.0, 12.0),
    "rotacion_cuentas_cobrar": (6.0, 10.0, 15.0),
    "dso": (30.0, 45.0, 60.0),
    "pe": (10.0, 20.0, 35.0),
    "pb": (1.0, 2.5, 5.0),
    "ps": (1.0, 3.0, 8.0),
    "ev_ebitda": (6.0, 12.0, 20.0),
    "peg": (0.5, 1.0, 2.0),
}

# Ratios que se muestran como porcentaje (el resto, como múltiplo "x.xx").
_PORCENTAJE = {"roe", "roa", "margen_bruto", "margen_operativo", "margen_neto"}
# Ratios de valuación: "alto" no es bueno ni malo, indica un múltiplo más exigente.
_VALUACION = {"pe", "pb", "ps", "ev_ebitda", "peg"}


# ---------------------------------------------------------------------------
# Extracción de conceptos desde el JSON de companyfacts.
# ---------------------------------------------------------------------------
def _units_de_concepto(facts: dict, concepto: str) -> dict | None:
    """Devuelve el dict de unidades de un concepto, buscándolo en us-gaap y dei."""
    bloques = facts.get("facts", {})
    for ns in ("us-gaap", "dei"):
        try:
            return bloques[ns][concepto]["units"]
        except (KeyError, TypeError):
            continue
    return None


def _observaciones(facts: dict, concepto: str, unidad: str = "USD") -> list[dict]:
    """Lista de observaciones de un concepto en la unidad pedida (vacía si no hay)."""
    units = _units_de_concepto(facts, concepto)
    if not units:
        return []
    if unidad in units:
        return units[unidad]
    # Fallback: primera unidad disponible (algunas cuentas usan 'USD/shares', etc.).
    for obs in units.values():
        return obs
    return []


def _dias(inicio: str, fin: str) -> int:
    """Días entre dos fechas ISO (yyyy-mm-dd)."""
    return (date.fromisoformat(fin) - date.fromisoformat(inicio)).days


def _ultimo_anual(facts: dict, conceptos: list[str]) -> dict | None:
    """Último valor de un FLUJO en base anual (~365 días), el de fecha de fin más reciente.

    Recorre TODOS los conceptos candidatos y se queda con la observación de 'end' más
    reciente. Esto es clave porque los emisores MIGRAN de tag con el tiempo (p. ej. NVDA
    pasó de 'RevenueFromContractWithCustomerExcludingAssessedTax' a 'Revenues'): tomar el
    primer concepto con datos devolvería un valor rancio de hace varios años.
    """
    mejor = None
    for c in conceptos:
        for o in _observaciones(facts, c):
            ini, fin, val = o.get("start"), o.get("end"), o.get("val")
            if not (ini and fin and val is not None):
                continue
            if 330 <= _dias(ini, fin) <= 400:
                if mejor is None or fin > mejor["end"]:
                    mejor = {"val": float(val), "end": fin, "concepto": c}
    return mejor


def _serie_anual(facts: dict, conceptos: list[str]) -> list[tuple[str, float]]:
    """Serie de valores anuales (end, val) de más nuevo a más viejo, de un solo tag consistente.

    Elige el concepto cuyo dato anual más reciente sea el más nuevo (para no mezclar tags
    al medir crecimiento) y devuelve TODA su serie.
    """
    mejor_serie: dict[str, float] = {}
    mejor_fin = ""
    for c in conceptos:
        por_fin: dict[str, float] = {}
        for o in _observaciones(facts, c):
            ini, fin, val = o.get("start"), o.get("end"), o.get("val")
            if not (ini and fin and val is not None):
                continue
            if 330 <= _dias(ini, fin) <= 400:
                por_fin[fin] = float(val)
        if por_fin and max(por_fin) > mejor_fin:
            mejor_fin = max(por_fin)
            mejor_serie = por_fin
    return sorted(mejor_serie.items(), key=lambda kv: kv[0], reverse=True)


def _merge_obs(facts: dict, conceptos: list[str]) -> list[dict]:
    """Une las observaciones de FLUJO (con duración) de todos los conceptos candidatos.

    Deduplica por (start, end) — un mismo período puede venir bajo dos tags tras una
    migración; nos quedamos con uno. Devuelve dicts {start, end, val, dur}.
    """
    obs: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for c in conceptos:
        for o in _observaciones(facts, c):
            ini, fin, val = o.get("start"), o.get("end"), o.get("val")
            if not (ini and fin and val is not None):
                continue
            clave = (ini, fin)
            if clave in vistos:
                continue
            vistos.add(clave)
            obs.append({"start": ini, "end": fin, "val": float(val), "dur": _dias(ini, fin)})
    return obs


def _ttm(facts: dict, conceptos: list[str]) -> dict | None:
    """Flujo TTM (trailing twelve months) por roll-forward.

    ★ POR QUÉ ROLL-FORWARD Y NO "SUMAR 4 TRIMESTRES" ★
    En XBRL rara vez existe un Q4 discreto: el 10-K reporta el AÑO completo, no el
    cuarto trimestre por separado, así que sumar los 4 últimos trimestres suele dejar
    un hueco. El método estándar evita eso:

        TTM = último año fiscal (A)
            + acumulado del año en curso (YTD_actual)
            − mismo acumulado un año antes (YTD_previo)

    Ej.: si cerró el FY en enero y ya reportó el 1er trimestre del año siguiente,
    TTM = FY + Q1_nuevo − Q1_viejo (corre la ventana 12m hacia adelante).

    Devuelve {'val', 'end'} (end = fin del período TTM) o None si no hay datos anuales.
    Si no hay nada más nuevo que el último anual, devuelve el anual tal cual.
    """
    obs = _merge_obs(facts, conceptos)
    if not obs:
        return None

    anuales = [o for o in obs if 330 <= o["dur"] <= 400]
    if not anuales:
        return None  # sin base anual no se puede hacer roll-forward → el caller cae a otra cosa
    base = max(anuales, key=lambda o: o["end"])
    fin_base = base["end"]

    # Acumulado del año en curso: empieza ~al inicio del nuevo año fiscal (start ≈ fin_base)
    # y termina después del último cierre anual. Tomamos el de fin más reciente.
    en_curso = [o for o in obs if o["end"] > fin_base and abs(_dias(fin_base, o["start"])) <= 20]
    if not en_curso:
        return {"val": base["val"], "end": fin_base}  # nada más nuevo → el anual
    ytd_actual = max(en_curso, key=lambda o: o["end"])

    # Mismo acumulado un año antes: misma duración (±25 días) y fin ≈ 1 año antes.
    objetivo = date.fromisoformat(ytd_actual["end"]) - timedelta(days=365)
    candidatos = [
        o for o in obs
        if abs(o["dur"] - ytd_actual["dur"]) <= 25
        and abs((date.fromisoformat(o["end"]) - objetivo).days) <= 20
    ]
    if not candidatos:
        return {"val": base["val"], "end": fin_base}  # no se puede emparejar → el anual
    ytd_previo = min(candidatos, key=lambda o: abs((date.fromisoformat(o["end"]) - objetivo).days))

    return {"val": base["val"] + ytd_actual["val"] - ytd_previo["val"], "end": ytd_actual["end"]}


def _flujo(facts: dict, conceptos: list[str]) -> dict | None:
    """Mejor valor de un flujo: TTM si se puede reconstruir; si no, el último anual."""
    t = _ttm(facts, conceptos)
    if t is not None:
        return t
    return _ultimo_anual(facts, conceptos)


def _ultimo_instante(facts: dict, conceptos: list[str], unidad: str = "USD") -> dict | None:
    """Último valor de un STOCK de balance (instantáneo), el de 'end' más reciente.

    Igual que `_ultimo_anual`: busca en todos los conceptos candidatos y toma el más
    reciente, para tolerar migraciones de tag entre filings.
    """
    mejor = None
    for c in conceptos:
        for o in _observaciones(facts, c, unidad):
            fin, val = o.get("end"), o.get("val")
            if not (fin and val is not None):
                continue
            if mejor is None or fin > mejor["end"]:
                mejor = {"val": float(val), "end": fin, "concepto": c}
    return mejor


# ---------------------------------------------------------------------------
# Cálculo e interpretación.
# ---------------------------------------------------------------------------
def _div(num: float | None, den: float | None) -> float | None:
    """División segura: None si falta algún operando o el denominador es ~0."""
    if num is None or den is None or den == 0:
        return None
    return num / den


def _interpretar(clave: str, valor: float | None) -> str:
    """Lectura cualitativa del ratio contra el benchmark genérico (en español)."""
    if valor is None:
        return "datos insuficientes"
    bm = _BENCHMARKS.get(clave)
    if not bm:
        return ""
    bajo, tipico, alto = bm

    if clave == "dso":  # inverso: menos días es mejor
        if valor <= bajo:
            return "excelente — cobranza muy rápida"
        if valor <= tipico:
            return "buena — dentro de lo normal"
        if valor <= alto:
            return "aceptable — vigilar la cobranza"
        return "atención — cobranza más lenta que sus pares"

    if clave == "deuda_patrimonio":  # menos apalancamiento suele ser mejor
        if valor <= bajo:
            return "apalancamiento conservador"
        if valor <= tipico:
            return "apalancamiento moderado"
        if valor <= alto:
            return "apalancamiento elevado — vigilar deuda"
        return "apalancamiento alto — riesgo financiero potencial"

    if clave in _VALUACION:  # neutro: "alto" = múltiplo exigente, no algo bueno/malo
        if valor < bajo:
            return "múltiplo bajo (barato vs. referencia)"
        if valor <= tipico:
            return "múltiplo moderado"
        if valor <= alto:
            return "múltiplo elevado"
        return "múltiplo muy exigente"

    # Resto: más alto = mejor (margen, rentabilidad, liquidez, cobertura, rotación).
    if valor < bajo:
        return "por debajo del promedio"
    if valor <= tipico:
        return "dentro de lo normal"
    if valor <= alto:
        return "por encima del promedio"
    return "muy por encima de sus pares"


def _unidad(clave: str) -> str:
    """Unidad de display del ratio: '%', 'días' o 'x' (múltiplo)."""
    if clave in _PORCENTAJE:
        return "%"
    if clave == "dso":
        return "días"
    return "x"


def _ratio(clave: str, nombre: str, formula: str, valor: float | None) -> dict:
    """Empaqueta un ratio para la UI/JSON."""
    return {
        "nombre": nombre,
        "valor": valor,
        "formula": formula,
        "interpretacion": _interpretar(clave, valor),
        "unidad": _unidad(clave),
    }


def compute_ratios(facts: dict, market: dict | None = None) -> dict:
    """Calcula las 5 categorías de ratios desde companyfacts de SEC.

    Parameters
    ----------
    facts : JSON de companyfacts de SEC EDGAR (SecEdgarSource.get_facts).
    market : datos de mercado opcionales para valuación, con claves posibles
        'market_cap' y 'share_price' (típicamente de la ficha yfinance). Sin esto,
        la categoría 'valuacion' queda con datos insuficientes.

    Returns
    -------
    dict serializable con: 'categorias' (5 categorías de ratios), 'as_of' (fechas de
    los datos por bloque), 'faltantes' (conceptos no hallados) y 'fuente'.
    """
    market = market or {}

    # --- Flujos (TTM: trailing twelve months; cae a último anual si no se puede) ---
    rev = _flujo(facts, _REVENUE)
    cogs = _flujo(facts, _COGS)
    op_inc = _flujo(facts, _OPERATING_INCOME)
    net_inc = _flujo(facts, _NET_INCOME)
    int_exp = _flujo(facts, _INTEREST_EXPENSE)
    da = _flujo(facts, _DEP_AMORT)
    ocf = _flujo(facts, _OPERATING_CASH_FLOW)

    revenue = rev["val"] if rev else None
    cogs_v = cogs["val"] if cogs else None
    operating_income = op_inc["val"] if op_inc else None
    net_income = net_inc["val"] if net_inc else None
    interest_expense = abs(int_exp["val"]) if int_exp else None  # se reporta negativo a veces
    dep_amort = da["val"] if da else None
    operating_cf = ocf["val"] if ocf else None

    gross_profit = (revenue - cogs_v) if (revenue is not None and cogs_v is not None) else None
    ebitda = (
        operating_income + dep_amort
        if (operating_income is not None and dep_amort is not None)
        else None
    )

    # --- Stocks de balance (último instante) ---
    assets = _ultimo_instante(facts, _ASSETS)
    cur_assets = _ultimo_instante(facts, _CURRENT_ASSETS)
    cur_liab = _ultimo_instante(facts, _CURRENT_LIABILITIES)
    equity = _ultimo_instante(facts, _EQUITY)
    cash = _ultimo_instante(facts, _CASH)
    inventory = _ultimo_instante(facts, _INVENTORY)
    receivables = _ultimo_instante(facts, _RECEIVABLES)
    ltd_nc = _ultimo_instante(facts, _LT_DEBT_NONCURRENT)
    ltd_c = _ultimo_instante(facts, _LT_DEBT_CURRENT)

    total_assets = assets["val"] if assets else None
    current_assets = cur_assets["val"] if cur_assets else None
    current_liabilities = cur_liab["val"] if cur_liab else None
    total_equity = equity["val"] if equity else None
    cash_v = cash["val"] if cash else None
    inventory_v = inventory["val"] if inventory else None
    receivables_v = receivables["val"] if receivables else None
    total_debt = None
    if ltd_nc or ltd_c:
        total_debt = (ltd_nc["val"] if ltd_nc else 0.0) + (ltd_c["val"] if ltd_c else 0.0)

    # --- Mercado (para valuación) ---
    market_cap = market.get("market_cap")
    enterprise_value = None
    if market_cap is not None and total_debt is not None and cash_v is not None:
        enterprise_value = market_cap + total_debt - cash_v
    # Crecimiento de ganancias (para PEG): de la serie anual de resultado neto.
    serie_ni = _serie_anual(facts, _NET_INCOME)
    growth = None
    if len(serie_ni) >= 2 and serie_ni[1][1] > 0:
        growth = serie_ni[0][1] / serie_ni[1][1] - 1.0

    pe = _div(market_cap, net_income)
    peg = None
    if pe is not None and growth is not None and growth > 0:
        peg = pe / (growth * 100.0)

    categorias = {
        "rentabilidad": {
            "roe": _ratio("roe", "ROE (rentab. s/ patrimonio)", "Resultado neto / Patrimonio",
                          _div(net_income, total_equity)),
            "roa": _ratio("roa", "ROA (rentab. s/ activos)", "Resultado neto / Activos",
                          _div(net_income, total_assets)),
            "margen_bruto": _ratio("margen_bruto", "Margen bruto", "(Ingresos − Costo) / Ingresos",
                                   _div(gross_profit, revenue)),
            "margen_operativo": _ratio("margen_operativo", "Margen operativo",
                                       "Resultado operativo / Ingresos",
                                       _div(operating_income, revenue)),
            "margen_neto": _ratio("margen_neto", "Margen neto", "Resultado neto / Ingresos",
                                  _div(net_income, revenue)),
        },
        "liquidez": {
            "ratio_corriente": _ratio("ratio_corriente", "Ratio corriente",
                                      "Activo corriente / Pasivo corriente",
                                      _div(current_assets, current_liabilities)),
            "ratio_rapido": _ratio("ratio_rapido", "Ratio rápido (prueba ácida)",
                                   "(Activo corriente − Inventario) / Pasivo corriente",
                                   _div((current_assets - inventory_v)
                                        if (current_assets is not None and inventory_v is not None)
                                        else None, current_liabilities)),
            "ratio_caja": _ratio("ratio_caja", "Ratio de caja", "Caja / Pasivo corriente",
                                 _div(cash_v, current_liabilities)),
        },
        "apalancamiento": {
            "deuda_patrimonio": _ratio("deuda_patrimonio", "Deuda / Patrimonio",
                                       "Deuda total / Patrimonio",
                                       _div(total_debt, total_equity)),
            "cobertura_intereses": _ratio("cobertura_intereses", "Cobertura de intereses",
                                          "Resultado operativo / Intereses",
                                          _div(operating_income, interest_expense)),
            "dscr": _ratio("dscr", "Cobertura del servicio de deuda",
                           "Flujo de caja operativo / Intereses",
                           _div(operating_cf, interest_expense)),
        },
        "eficiencia": {
            "rotacion_activos": _ratio("rotacion_activos", "Rotación de activos",
                                       "Ingresos / Activos", _div(revenue, total_assets)),
            "rotacion_inventario": _ratio("rotacion_inventario", "Rotación de inventario",
                                          "Costo / Inventario", _div(cogs_v, inventory_v)),
            "rotacion_cuentas_cobrar": _ratio("rotacion_cuentas_cobrar", "Rotación de cuentas por cobrar",
                                              "Ingresos / Cuentas por cobrar",
                                              _div(revenue, receivables_v)),
            "dso": _ratio("dso", "Días de venta pendientes (DSO)", "365 / Rotación de cuentas por cobrar",
                          _div(365.0, _div(revenue, receivables_v))),
        },
        "valuacion": {
            "pe": _ratio("pe", "P/E (precio / ganancias)", "Capitalización / Resultado neto", pe),
            "pb": _ratio("pb", "P/B (precio / valor libro)", "Capitalización / Patrimonio",
                         _div(market_cap, total_equity)),
            "ps": _ratio("ps", "P/S (precio / ventas)", "Capitalización / Ingresos",
                         _div(market_cap, revenue)),
            "ev_ebitda": _ratio("ev_ebitda", "EV / EBITDA", "Valor empresa / EBITDA",
                                _div(enterprise_value, ebitda)),
            "peg": _ratio("peg", "PEG (P/E ajustado por crecimiento)", "P/E / crecimiento de ganancias (%)",
                          peg),
        },
    }

    # Fechas as-of por bloque (de cuándo es el dato que se está mostrando).
    as_of = {
        "flujos_ttm": rev["end"] if rev else (net_inc["end"] if net_inc else None),
        "balance": assets["end"] if assets else (equity["end"] if equity else None),
    }

    # Conceptos clave que no se encontraron (transparencia de completitud).
    faltantes: list[str] = []
    for etiqueta, dato in [
        ("ingresos", revenue), ("costo", cogs_v), ("resultado operativo", operating_income),
        ("resultado neto", net_income), ("activos", total_assets),
        ("pasivo corriente", current_liabilities), ("patrimonio", total_equity),
        ("inventario", inventory_v), ("deuda", total_debt),
        ("flujo de caja operativo", operating_cf), ("capitalización (mercado)", market_cap),
    ]:
        if dato is None:
            faltantes.append(etiqueta)

    return {
        "categorias": categorias,
        "as_of": as_of,
        "faltantes": faltantes,
        "fuente": "SEC EDGAR (companyfacts XBRL) · flujos = TTM (últimos 12 meses)",
    }


_ETIQUETAS_CATEGORIA = {
    "rentabilidad": "Rentabilidad",
    "liquidez": "Liquidez",
    "apalancamiento": "Apalancamiento",
    "eficiencia": "Eficiencia",
    "valuacion": "Valuación",
}


def format_ratio_value(valor: float | None, unidad: str = "x") -> str:
    """Formatea un valor de ratio para mostrar ('—' si None)."""
    if valor is None:
        return "—"
    if unidad == "%":
        return f"{valor * 100:.1f}%"
    if unidad == "días":
        return f"{valor:.0f} días"
    return f"{valor:.2f}x"


if __name__ == "__main__":  # prueba manual: python -m analysis.financial_ratios NVDA
    import sys

    from data_sources.fundamentals import SecEdgarSource
    from data_sources.profile import YFinanceProfileSource

    tk = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    facts = SecEdgarSource().get_facts(tk)
    market = {}
    try:
        p = YFinanceProfileSource().get_profile(tk)
        market = {"market_cap": p.market_cap, "share_price": p.precio}
    except Exception:
        pass

    out = compute_ratios(facts, market)
    print(f"\n=== Ratios {tk} · balance {out['as_of']['balance']} · "
          f"flujos TTM al {out['as_of']['flujos_ttm']} ===")
    for cat, ratios in out["categorias"].items():
        print(f"\n--- {_ETIQUETAS_CATEGORIA[cat]} ---")
        for r in ratios.values():
            print(f"  {r['nombre']:38} {format_ratio_value(r['valor'], r['unidad']):>10}"
                  f"   {r['interpretacion']}")
    if out["faltantes"]:
        print(f"\nConceptos no hallados: {', '.join(out['faltantes'])}")
