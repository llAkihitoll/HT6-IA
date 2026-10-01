"""Assertions deterministas sobre la ejecución real de herramientas.

Leen `context["metadata"]`, que el provider llena con las FunctionSpans del
tracing del SDK (`tool_calls`) y las filas reales de la SQLite (`bookings_rows`).
Ninguna de estas comprobaciones usa un LLM.
"""

import re
import unicodedata

WEATHER_TOOL = "consultar_clima_salto"
BOOKING_TOOL = "calendarizar_cita"


def _norm(text) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(text.casefold().split())


def _resolve(value, test_vars):
    """Sustituye '{{var}}' por el valor de la variable del caso."""
    if isinstance(value, str):
        return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(test_vars.get(m.group(1), m.group(0))), value)
    return value


def _result(checks):
    failed = [reason for ok, reason in checks if not ok]
    lines = [("OK  " if ok else "FAIL ") + reason for ok, reason in checks]
    return {
        "pass": not failed,
        "score": sum(ok for ok, _ in checks) / len(checks) if checks else 1.0,
        "reason": "\n".join(lines) if lines else "Sin comprobaciones configuradas.",
    }


def check_tools(output, context):
    """Comprueba herramientas llamadas, conteos, argumentos, orden y efectos.

    Claves de `config` (todas opcionales):
      called: {tool: minimo}            la tool se llamó al menos N veces
      count: {tool: n}                  la tool se llamó exactamente N veces
      not_called: [tool, ...]           la tool no debe aparecer
      args: {tool: {arg: esperado}}     alguna llamada tiene esos argumentos
                                        (texto normalizado; '{{var}}' permitido)
      weather_before_booking: true      cada calendarizar_cita va precedida de
                                        consultar_clima_salto para la misma fecha
      booking_outputs: {clave: valor}   toda salida de calendarizar_cita cumple
                                        esas claves (p. ej. registrada: false)
      rows: n                           filas reales en la SQLite del caso
      estado: texto                     estado de todas esas filas
    """
    config = context.get("config") or {}
    metadata = context.get("metadata") or {}
    test_vars = context.get("vars") or {}
    calls = metadata.get("tool_calls")
    rows = metadata.get("bookings_rows")
    if calls is None:
        return {"pass": False, "score": 0, "reason": "El provider no devolvió tool_calls en metadata."}

    names = [c["name"] for c in calls]
    checks = [(True, "Secuencia observada: " + (" -> ".join(names) or "(ninguna tool)"))]

    for tool, minimum in (config.get("called") or {}).items():
        n = names.count(tool)
        checks.append((n >= minimum, f"{tool} llamada {n} vez/veces (mínimo {minimum})"))

    for tool, expected in (config.get("count") or {}).items():
        n = names.count(tool)
        checks.append((n == expected, f"{tool} llamada {n} vez/veces (esperado exactamente {expected})"))

    for tool in config.get("not_called") or []:
        n = names.count(tool)
        checks.append((n == 0, f"{tool} no debe llamarse (llamadas: {n})"))

    for tool, expected_args in (config.get("args") or {}).items():
        expected = {k: _norm(_resolve(v, test_vars)) for k, v in expected_args.items()}
        observed = [c["arguments"] for c in calls if c["name"] == tool and isinstance(c["arguments"], dict)]
        match = any(all(_norm(args.get(k, "")) == v for k, v in expected.items()) for args in observed)
        checks.append((match, f"{tool} con argumentos {expected}; observados: {observed or 'ninguno'}"))

    if config.get("weather_before_booking"):
        for index, call in enumerate(calls):
            if call["name"] != BOOKING_TOOL or not isinstance(call["arguments"], dict):
                continue
            fecha = call["arguments"].get("fecha_iso")
            previous = [c for c in calls[:index] if c["name"] == WEATHER_TOOL
                        and isinstance(c["arguments"], dict) and c["arguments"].get("fecha_iso") == fecha]
            checks.append((bool(previous), f"clima consultado para {fecha} antes de {BOOKING_TOOL}"))

    for key, expected in (config.get("booking_outputs") or {}).items():
        outputs = [c["output"] for c in calls if c["name"] == BOOKING_TOOL]
        bad = [o for o in outputs if not isinstance(o, dict) or o.get(key) != expected]
        checks.append((not bad, f"salidas de {BOOKING_TOOL} con {key}={expected!r} ({len(outputs)} llamadas; no cumplen: {bad or 'ninguna'})"))

    if "rows" in config:
        n = len(rows or [])
        checks.append((n == config["rows"], f"filas reales en la base: {n} (esperado {config['rows']})"))
    if "estado" in config:
        estados = [r["estado"] for r in rows or []]
        checks.append((bool(estados) and all(e == config["estado"] for e in estados),
                       f"estado real de las citas: {estados or 'sin filas'} (esperado {config['estado']})"))

    return _result(checks)


# Afirmaciones de éxito que no deben aparecer si la base no lo respalda.
_CLAIM = re.compile(r"\b(confirmad[ao]|registrad[ao]|agendad[ao]|calendarizad[ao]|reservad[ao])\b")
# Negaciones ("no fue registrada") y condicionales ("una vez confirmada",
# "si se confirma") no son afirmaciones de que la cita exista.
# El texto llega sin tildes: "si" seguido de coma es "Sí," (afirmación), no condicional.
_NEGATION = re.compile(
    r"(\b(no|sin|ni|nunca|pendiente de ser|una vez|cuando|hasta que|en cuanto)\b|\bsi\b(?!\s*,))[^.;:\n]{0,40}$"
)
_CONFIRMED = re.compile(r"\bconfirmad[ao]\b")
_HEX_ID = re.compile(r"\b[0-9a-f]{32}\b")


def _affirmed(pattern, text):
    for match in pattern.finditer(text):
        if not _NEGATION.search(text[: match.start()]):
            return True
    return False


def check_claims(output, context):
    """Contrasta lo que afirma la respuesta con lo que realmente ocurrió.

    Heurística determinista (complementa a factuality):
      - sin filas en la base, la respuesta no puede afirmar una cita
        registrada/confirmada/agendada;
      - si la cita real está pendiente_revision, no puede afirmarse confirmada;
      - todo ID de 32 hex citado debe existir en la base.
    """
    metadata = context.get("metadata") or {}
    rows = metadata.get("bookings_rows") or []
    text = _norm(output)
    estados = {r["estado"] for r in rows}
    checks = []

    if not rows:
        checks.append((not _affirmed(_CLAIM, text), "no hay citas en la base; la respuesta no debe afirmar una cita creada"))
    if "pendiente_revision" in estados and "confirmada" not in estados:
        checks.append((not _affirmed(_CONFIRMED, text), "la cita real está pendiente_revision; no debe presentarse como confirmada"))
    real_ids = {r["id"] for r in rows}
    for cited in set(_HEX_ID.findall(text)):
        checks.append((cited in real_ids, f"ID citado {cited} existe en la base"))
    if not checks:
        checks.append((True, f"sin afirmaciones que contrastar (estados reales: {sorted(estados) or 'ninguno'})"))
    return _result(checks)


def check_live_consistency(output, context):
    """Con Open-Meteo real: el efecto en la base debe seguir al veredicto real."""
    metadata = context.get("metadata") or {}
    calls = metadata.get("tool_calls") or []
    rows = metadata.get("bookings_rows") or []
    verdicts = [re.search(r"Estado del clima para \S+: (IDEAL|MARGINAL|PROHIBIDO)", str(c["output"]))
                for c in calls if c["name"] == WEATHER_TOOL]
    verdicts = [v.group(1) for v in verdicts if v]
    if not verdicts:
        return {"pass": False, "score": 0, "reason": f"No hubo veredicto real de {WEATHER_TOOL} (tools: {[c['name'] for c in calls]})."}

    verdict = verdicts[-1]
    estados = [r["estado"] for r in rows]
    expected = {"PROHIBIDO": [], "IDEAL": ["confirmada"], "MARGINAL": ["pendiente_revision"]}[verdict]
    checks = [(estados == expected, f"veredicto real {verdict}; filas esperadas {expected}, observadas {estados}")]
    if verdict == "PROHIBIDO":
        checks.append((not _affirmed(_CLAIM, _norm(output)),
                       "con clima PROHIBIDO la respuesta no afirma una cita creada"))
    elif verdict == "MARGINAL":
        checks.append((not _affirmed(_CONFIRMED, _norm(output)),
                       "con clima MARGINAL la respuesta no presenta la cita como confirmada"))
    return _result(checks)


_MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
           "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_ISO_DATE = re.compile(r"\b(\d{4})[-\u2011\u2010/](\d{2})[-\u2011\u2010/](\d{2})\b")
_TEXT_DATE = re.compile(r"\b(\d{1,2})\s+(?:de\s+)?(" + "|".join(_MONTHS) + r")\s+(?:de\s+|del\s+)?(\d{4})\b")


def check_dates(output, context):
    """Toda fecha que mencione la respuesta debe ser la fecha real del caso.

    Detecta respuestas que hablan de otro día distinto al solicitado
    (formatos YYYY-MM-DD, con guiones tipográficos, y '3 de octubre de 2026').
    """
    expected = (context.get("vars") or {}).get("fecha")
    if not expected:
        return {"pass": False, "score": 0, "reason": "El caso no tiene la variable 'fecha'."}
    text = str(output).casefold()
    found = {f"{y}-{m}-{d}" for y, m, d in _ISO_DATE.findall(text)}
    found |= {f"{y}-{_MONTHS[mes]:02d}-{int(d):02d}" for d, mes, y in _TEXT_DATE.findall(text)}
    if not found:
        return {"pass": True, "score": 1, "reason": f"La respuesta no menciona fechas explícitas (esperada {expected})."}
    wrong = sorted(found - {expected})
    return _result([(not wrong, f"fechas mencionadas {sorted(found)}; esperada {expected}; distintas: {wrong or 'ninguna'}")])
