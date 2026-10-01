"""Hook de Promptfoo: convierte fechas relativas en fechas ISO reales.

El clima solo acepta fechas entre hoy y hoy + 15 días (America/Guatemala),
así que los datasets usan `offset_dias` en vez de fechas fijas. Antes de cada
caso se calcula `fecha` y se sustituye `{fecha}` en el mensaje y en la cita
precargada. Las assertions pueden usar `{{fecha}}` normalmente.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def extension_hook(hook_name, context):
    if hook_name != "beforeEach":
        return None
    test = context["test"]
    test_vars = dict(test.get("vars") or {})
    if "offset_dias" not in test_vars:
        return None

    today = datetime.now(ZoneInfo("America/Guatemala")).date()
    fecha = (today + timedelta(days=int(test_vars["offset_dias"]))).isoformat()
    test_vars["fecha"] = fecha
    test_vars["mensaje"] = test_vars["mensaje"].replace("{fecha}", fecha)
    if test_vars.get("precargar_reserva"):
        seed = dict(test_vars["precargar_reserva"])
        seed["fecha"] = seed["fecha"].replace("{fecha}", fecha)
        test_vars["precargar_reserva"] = seed
    return {"test": {**test, "vars": test_vars}}
