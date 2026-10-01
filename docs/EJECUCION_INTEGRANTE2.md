> Nota de integración: las FAQs y reservas provisionales fueron sustituidas
> por los módulos compartidos del integrante 3. Consulta el README actual
> para instalar PostgreSQL y cargar el corpus antes de ejecutar esta arquitectura.

# Instrucciones de ejecución — Arquitectura jerárquica (Integrante 2)

Esta sección cubre únicamente la parte del Integrante 2 (arquitectura
jerárquica + evaluador climático compartido). No reemplaza el README
final del equipo: está pensada para que el Integrante 1 la incorpore ahí
junto con las secciones de las otras dos arquitecturas.

## 1. Requisitos

- Python 3.11 o superior.
- Una API key de OpenAI (para ejecutar el programa demo, que sí llama a
  un modelo real). Las pruebas automatizadas **no** requieren API key.

## 2. Instalación

Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
```

Esto instala `openai-agents` (SDK de agentes), `pytest` (pruebas) y
`python-dotenv` (carga de variables de entorno).

## 3. Configuración

Copia el archivo de ejemplo y coloca tu API key:

```bash
cp .env.example .env
```

Edita `.env` y reemplaza el valor de ejemplo:

```
OPENAI_API_KEY=sk-tu-api-key-real
```

No es necesario configurar nada más para esta parte: las coordenadas del
sitio de aterrizaje (14.013722, -90.771611) y los umbrales climáticos
están fijos en el código (`shared/weather_evaluator.py`), tal como los
define el enunciado.

## 4. Ejecutar el programa demo

Desde la raíz del repositorio:

```bash
python -m hierarchical.main
```

Esto ejecuta 4 consultas de ejemplo a través del Supervisor General,
mostrando cómo delega a cada rama de la jerarquía:

1. Una pregunta frecuente (FAQs).
2. Una consulta de clima dentro del horizonte de pronóstico (16 días).
3. Una solicitud de calendarización, que primero verifica el clima antes
   de confirmar la cita.
4. Una consulta de clima fuera del horizonte de pronóstico de Open-Meteo,
   para mostrar el manejo de esa limitación.

**Nota de integración:** el proveedor simulado fue reemplazado por
`shared/open_meteo_client.py`, la integración real del Integrante 1. Los
agentes de FAQs y Reservas continúan como placeholders hasta que el Integrante
3 entregue sus módulos definitivos.

## 5. Ejecutar las pruebas

Las pruebas del evaluador climático (`tests/test_weather_evaluator.py`)
son puramente unitarias, no requieren API key ni conexión a internet:

```bash
python -m pytest tests/ -v
```

Salida esperada: 26 pruebas, todas en verde, cubriendo:

- Cada umbral (viento sostenido, ráfagas, precipitación, cobertura de
  nubes) con un valor dentro del rango, en el límite exacto, e
  inmediatamente fuera del límite.
- Escenarios combinados: condiciones completamente ideales, marginales,
  prohibidas por una sola variable, y prohibidas por múltiples variables
  simultáneamente.
- Que los motivos y restricciones reportados sean los correctos según el
  enunciado.

## 6. Ejemplos de consultas para probar manualmente

Si quieres experimentar más allá de las 4 consultas fijas del demo, edita
`hierarchical/main.py` (lista `DEMO_QUERIES`) o escribe tu propio script:

```python
from agents import Runner
from hierarchical.supervisor import supervisor

result = Runner.run_sync(
    supervisor,
    "¿Puedo saltar mañana? Si el clima lo permite, calendariza mi cita, me llamo Carlos.",
)
print(result.final_output)
```

Ejemplos de mensajes útiles para ver cada rama de la jerarquía en acción:

- FAQs: `"¿Puedo cancelar mi cita?"`
- Clima ideal/marginal/prohibido: cambia la fecha en un mensaje como
  `"¿El clima permite saltar el YYYY-MM-DD?"`. El resultado proviene del
  pronóstico real de Open-Meteo, por lo que puede variar entre ejecuciones.
- Reservas: `"Calendariza mi salto para el YYYY-MM-DD, mi nombre es ..."`
  y observa cómo el Submanager consulta el clima antes de confirmar.

## 7. Alcance de esta parte

Esta implementación cubre la responsabilidad del Integrante 2: arquitectura
jerárquica, evaluador climático compartido y pruebas de límites. La integración
real con Open-Meteo ya fue incorporada como módulo compartido por el Integrante
1. Las FAQs reales, el almacenamiento definitivo y la arquitectura
descentralizada corresponden al Integrante 3.
