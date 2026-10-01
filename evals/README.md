# HT6 — Evals del agente de Parachute S.A. con Promptfoo

Evaluación reproducible del agente construido en la Hoja de trabajo #5, antes
de llevarlo a producción. Se evalúan sus dos funcionalidades —**preguntas
frecuentes** y **agendamiento de citas**— con cuatro familias de graders:
factuality, deterministas (contains/regex), latencia y ejecución de
herramientas.

Reporte entregable (generado por Promptfoo, ejecución real):

- [`reports/report.html`](reports/report.html) — reporte visual.
- [`reports/results.json`](reports/results.json) — resultados completos: salidas,
  razones de cada grader, latencias, tokens y la metadata con las tool calls.
- [`reports/run1/`](reports/run1/) — primera ejecución completa, conservada como
  evidencia (ver [Historial de ejecuciones](#historial-de-ejecuciones)).

## 1. Qué se evalúa

**Arquitectura jerárquica de la HT5**, la que el equipo eligió en
`docs/RESPUESTAS.md` ("preferimos la arquitectura jerárquica"). El código del
agente se copió sin cambios desde `HT5-IA` (`origin/master`, commit `68c5783`).
Los evals ejecutan el sistema real; no hay un agente paralelo para evaluar.

```
Usuario
  └─ Supervisor General                    hierarchical/supervisor.py
       ├─ responder_faq ─────────── Agente FAQs ── buscar_faq ── pgvector (120 FAQs, Lab 4)
       └─ gestionar_operaciones ─── Submanager Operaciones
              ├─ consultar_clima ──── Agente Clima ── consultar_clima_salto ── Open-Meteo + weather_evaluator
              └─ gestionar_reserva ── Agente Reservas ── calendarizar_cita ── bookings.create_booking (SQLite)
```

Todas las delegaciones son `Agent.as_tool()` del SDK `openai-agents` 0.22.3.
`calendarizar_cita` vuelve a consultar y evaluar el clima en código antes de
escribir: con clima prohibido no guarda nada, con marginal deja la cita
`pendiente_revision` y con ideal la deja `confirmada`.

## 2. Instalación

Requisitos: Python 3.11+ (probado con 3.13), Node.js ≥ 22.22 (requisito de
Promptfoo 0.123.1), Docker con Compose y una API key de NVIDIA NIM.

```bash
# Desde la raíz de HT6
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
npm install                     # instala promptfoo 0.123.1 (versión fijada en package.json)
```

Copia `.env.example` a `.env` y completa **solo** `NVIDIA_API_KEY`
(https://build.nvidia.com/settings/api-keys). `.env` está en `.gitignore`.

### Servicios

| Servicio | Cómo | Notas |
|---|---|---|
| PostgreSQL + pgvector | `POSTGRES_PORT=5434 docker compose up -d --wait` (PowerShell: `$env:POSTGRES_PORT=5434; docker compose up -d --wait`) | HT6 usa el puerto 5434 porque el 5433 puede estar ocupado por otro contenedor |
| Corpus de FAQs | `DATABASE_URL=postgresql://parachute:parachute_local@localhost:5434/parachute_faqs python -m shared.faq_store.load_data` | Debe terminar con "120 filas, 6 categorías". La primera vez descarga el modelo de embeddings |
| NVIDIA NIM | API externa | Ejecuta el modelo del agente y el grader |
| Open-Meteo | API externa sin key | Solo la usa el caso R8 (clima real) |

## 3. Ejecutar los evals y generar el reporte

Con el venv activado (Promptfoo usa el `python` del PATH; también se puede
definir `PROMPTFOO_PYTHON` con la ruta al Python del venv):

```bash
npm run eval        # = promptfoo eval -c evals/promptfooconfig.yaml --no-cache \
                    #     -o evals/reports/report.html -o evals/reports/results.json
npm run eval:view   # visor web local de Promptfoo
```

- `--no-cache` es obligatorio: con caché, Promptfoo reutilizaría respuestas y
  la latencia dejaría de medir ejecuciones reales.
- Promptfoo devuelve **código de salida 100** cuando algún caso falla. Es lo
  esperado en un eval que detecta fallos, no un error de ejecución.
- Para correr un subconjunto: `npx promptfoo eval -c evals/promptfooconfig.yaml --no-cache --filter-pattern "^R1 "`.
- La ejecución completa tarda entre 30 y 45 minutos, con un caso a la vez.

Pruebas automatizadas (sin API ni red): `python -m pytest -q`. Incluyen las
74 pruebas originales de HT5 y 29 nuevas de los graders propios
(`tests/test_eval_assertions.py`).

## 4. Estructura

| Archivo | Rol |
|---|---|
| `promptfooconfig.yaml` | Provider, grader de factuality, hook, concurrencia y datasets |
| `provider.py` | Provider Python: ejecuta el Supervisor real y devuelve salida, latencia, tokens y metadata (tool calls y filas reales de la base) |
| `hooks.py` | Hook `beforeEach`: convierte `offset_dias` en la fecha real de Guatemala |
| `datasets/faq.yaml` | Casos F1–F7 |
| `datasets/reservations.yaml` | Casos R1–R8 |
| `assertions/tool_calls.py` | Graders deterministas en Python: `check_tools`, `check_claims`, `check_live_consistency`, `check_dates` |
| `../tests/test_eval_assertions.py` | Pruebas de esos graders y del hook |

### Integración con el agente (sin modificarlo)

- **Modelo.** Los agentes de la HT5 no fijan modelo. El provider lo inyecta con
  `RunConfig(model_provider=OpenAIProvider(base_url=NIM, use_responses=False), model=...)`,
  que el SDK propaga a todos los sub-agentes `as_tool`. Agente: `openai/gpt-oss-20b`.
- **Base de reservas aislada.** Cada caso escribe en una SQLite temporal propia
  (`BOOKINGS_DB`).
- **Escenarios climáticos.** Para probar ideal, marginal y prohibido de forma
  reproducible, el provider reemplaza **solo la frontera con Open-Meteo**
  (`fetch_weather_reading`) por una lectura fija. Es la misma técnica que ya
  usan `tests/test_bookings.py` y `tests/test_decentralized.py`. La validación
  real de fechas sigue ejecutándose. Las lecturas son las de esos tests y se
  presentan como escenarios, no como pronósticos:

  | Escenario | Viento | Ráfagas | Lluvia | Nubes | Veredicto del evaluador |
  |---|---|---|---|---|---|
  | `ideal` | 10 | 20 | 0 | 10 | IDEAL |
  | `marginal` | 20 | 35 | 0 | 10 | MARGINAL (solo tándem experimentado) |
  | `prohibido-lluvia` | 10 | 20 | 0.1 | 10 | PROHIBIDO |
  | `prohibido-rafagas` | 10 | 36 | 0 | 10 | PROHIBIDO |

  R5 y R8 usan `clima: live`, sin reemplazos.
- **Fechas.** El clima solo acepta desde hoy hasta hoy + 15 días, así que los casos
  declaran `offset_dias` y `hooks.py` calcula `fecha` antes de cada caso.

## 5. Graders

| Métrica en el reporte | Tipo Promptfoo | Qué comprueba |
|---|---|---|
| `factuality` | `factuality` (model-graded) | Consistencia de la respuesta con una referencia del corpus o de las reglas del sistema |
| `deterministic` | `contains`, `icontains`, `icontains-any`, `regex`, `not-regex` | Datos obligatorios, formatos y contenido prohibido (precios u horarios inventados) |
| `citation` | `regex` | Que la respuesta final cite el `FAQ-xxx` usado (las instrucciones del Agente FAQs exigen citarlo) |
| `latency` | `latency` | Tiempo de respuesta por debajo del umbral |
| `tool_execution` | `python` → `check_tools` | Tools llamadas o no llamadas, conteos, argumentos y orden (clima antes de reserva) |
| `estado_real` | `python` → `check_tools` | Efecto real: filas y estado en la SQLite y salida real de `calendarizar_cita` |
| `consistency` | `python` → `check_claims`, `check_dates`, `check_live_consistency` | Lo que **afirma** la respuesta frente a lo que **ocurrió** |

### Cómo se evaluó factuality

- **Grader:** `openai:chat:z-ai/glm-5.3` en NIM, con `temperature: 0`. Es un
  modelo distinto al del agente, para que el agente no se evalúe a sí mismo.
- **FAQ:** la referencia es el texto real del corpus, con el ID citado en cada
  caso. Solo 14 de las 120 FAQs tienen datos concretos; las demás son fichas
  plantilla que remiten a `soporte@parachutesa.gt`. En F6 y F7 (información no
  disponible) se configuró `options.factuality.superset: 0`, porque ahí
  añadir información equivale a inventar.
- **Reservas:** la referencia describe el resultado esperado según las reglas
  del sistema (por ejemplo, "quedó pendiente de revisión, no confirmada").
  Como el grader solo compara textos, se complementa con `check_claims`, que
  contrasta la respuesta con la base real:
  - si no hay filas, la respuesta no puede afirmar una cita creada;
  - una cita pendiente no puede presentarse como confirmada;
  - todo ID citado debe existir.

  Así se distinguen cuatro cosas: la respuesta del modelo, el resultado real de
  la tool, la referencia y el veredicto del grader.

### Cómo se evaluó la latencia

- **Qué se mide.** El provider mide el tiempo de `Runner.run` del Supervisor,
  que incluye todas las llamadas al LLM y a las tools de los tres niveles. Lo
  devuelve como `latencyMs`, una función documentada del provider Python de
  Promptfoo, y la assertion `latency` lo compara con el umbral.
- **Qué no se mide.** La preparación del harness (base temporal, escenario
  climático) y la carga del modelo de embeddings. Esta última ocurre una sola
  vez por worker, antes de iniciar el cronómetro.
- **Desglose.** En `metadata.tool_calls[].duration_ms` del JSON está la
  duración de cada tool.
- **Umbrales.** Los define esta evaluación; el proyecto no tenía ninguno:
  **FAQ ≤ 20 000 ms** y **reservas ≤ 45 000 ms**. Las reservas atraviesan dos
  niveles más de delegación con LLM que las FAQ.

### Cómo se verificaron las tool calls

- **Mecanismo.** Se usa el tracing nativo del SDK, que ya está activo en la
  arquitectura jerárquica; no se inventó un mecanismo propio. El provider
  registra un `TracingProcessor` con `set_trace_processors`, que además
  reemplaza al exportador por defecto, así que no salen trazas de la máquina.
- **Qué se recoge.** Cada `FunctionSpan` (nombre, argumentos, salida y
  duración), junto con el agente que la ejecutó, que se obtiene subiendo por
  la cadena `FunctionSpan → TurnSpan → AgentSpan`.
- **Por qué hace falta.** `result.new_items` solo muestra las tools del
  Supervisor; las de los sub-agentes `as_tool` únicamente aparecen en el
  tracing.
- **Ejemplo real (R1):**
  `gestionar_operaciones → consultar_clima → consultar_clima_salto(fecha_iso=2026-10-03) → gestionar_reserva → calendarizar_cita(fecha_iso=2026-10-03, nombre_cliente=Ana López, hora=10:00)`,
  con 1 fila `confirmada` en la base.

## 6. Matriz de evaluación (implementada)

| ID | Funcionalidad | Caso | Factuality | Contains | Regex | Latencia | Tool execution / estado real |
|---|---|---|---|---|---|---|---|
| F1 | FAQ | Peso máximo (FAQ-021) | ✓ | ✓ `100` | ✓ `100 kg`, cita | ✓ | `responder_faq`, `buscar_faq`; sin tools de operaciones |
| F2 | FAQ | Edad mínima (FAQ-023) | ✓ | ✓ `18` | ✓ `18 años`, cita | ✓ | ídem |
| F3 | FAQ | Espera tras bucear (FAQ-029) | ✓ | | ✓ `24 horas`, cita | ✓ | ídem |
| F4 | FAQ | Altura del salto (FAQ-049) | ✓ | | ✓ `3,000 m`, cita | ✓ | ídem |
| F5 | FAQ | Cámara personal (FAQ-081) | ✓ | ✓ negación | ✓ cita | ✓ | ídem |
| F6 | FAQ | Precio no disponible (FAQ-061, plantilla) | ✓ superset = fallo | ✓ correo de soporte | ✓ not-regex: precio inventado | ✓ | ídem |
| F7 | FAQ | Fuera del corpus (surf) | ✓ superset = fallo | | ✓ not-regex: precio u hora | ✓ | `buscar_faq` llamado; sin reservas |
| R1 | Reserva | Válida, clima ideal | ✓ | ✓ `confirmada` | ✓ ID de 32 hex | ✓ | clima antes de reservar; `calendarizar_cita`×1 con fecha, nombre y hora; 1 fila `confirmada`; consistencia y fechas |
| R2 | Reserva | Válida, clima marginal | ✓ | ✓ `experimentado` | ✓ `pendiente` | ✓ | `calendarizar_cita`×1; 1 fila `pendiente_revision`; no "confirmada" |
| R3 | Reserva | Rechazo por lluvia | ✓ | ✓ lluvia/precipitación | | ✓ | clima con la fecha; **sin** `calendarizar_cita`; 0 filas |
| R4 | Reserva | Rechazo por ráfagas | ✓ | ✓ ráfaga | ✓ `36 km/h` | ✓ | ídem R3 |
| R5 | Reserva | Fecha fuera del horizonte (+30 días) | ✓ | | ✓ `16 días` | ✓ | 0 filas; salidas de reserva `registrada:false` |
| R6 | Reserva | Datos incompletos | | ✓ `nombre` | | ✓ | **sin** `calendarizar_cita`; 0 filas |
| R7 | Reserva | Cita repetida (precargada) | ✓ | | | ✓ | `calendarizar_cita`×1 con `ya_existia:true`; sigue 1 fila |
| R8 | Reserva | Open-Meteo real | (sin referencia fija) | | | ✓ | clima con la fecha; base coherente con el veredicto real; fechas |

## 7. Resultados (ejecución final, 2026-10-01)

**10 de 15 casos pasan, 5 fallan y 0 errores**, en 28 min 35 s. Se usaron 97 143
tokens: 56 085 del agente y 41 058 del grader.

| Métrica | Assertions aprobadas |
|---|---|
| tool_execution | 14 / 14 |
| estado_real | 7 / 7 |
| consistency | 16 / 16 |
| deterministic | 18 / 19 |
| factuality | 11 / 13 |
| latency | 13 / 15 |
| citation | 3 / 5 |

| Caso | Resultado | Latencia | Motivo del fallo |
|---|---|---|---|
| F1 | PASS | 13.8 s | |
| F2 | PASS | 8.1 s | |
| F3 | FAIL | 10.3 s | El Supervisor eliminó la cita `FAQ-029` |
| F4 | FAIL | 13.6 s | El Supervisor eliminó la cita `FAQ-049` |
| F5 | PASS | 14.6 s | |
| F6 | FAIL | 20.9 s | Ver hallazgo 2 |
| F7 | PASS | 7.3 s | |
| R1 | PASS | 28.6 s | |
| R2 | FAIL | 53.3 s | Solo la latencia (umbral 45 s); el comportamiento fue correcto |
| R3 | PASS | 14.8 s | |
| R4 | PASS | 41.8 s | |
| R5 | PASS | 23.7 s | |
| R6 | PASS | 32.4 s | |
| R7 | FAIL | 22.3 s | Ver hallazgo 3 |
| R8 | PASS | 28.5 s | Open-Meteo real: PROHIBIDO, 0 filas |

**Latencia real.**
- FAQ: mínimo 7.3 s, mediana 13.6 s, media 12.7 s, máximo 20.9 s.
- Reservas: mínimo 14.8 s, mediana 28.6 s, media 30.7 s, máximo 53.2 s.
- Las tools finales (`buscar_faq`, `consultar_clima_salto`, `calendarizar_cita`)
  suman 1.9 s de 334 s totales (0.6 %). **Casi toda la latencia son llamadas
  al LLM:** 4 por FAQ y 6–9 por reserva. Es el costo de la capa extra de
  delegación de la jerárquica, que la HT5 había anticipado sin medirlo.

## 8. Hallazgos

Estos son fallos reales detectados por los evals. **No se corrigieron**:
esta actividad evalúa el agente, no lo reimplementa.

1. **El Supervisor pierde las citas de las FAQ.** El Agente FAQs incluye
   `FAQ-xxx`, pero el Supervisor a veces las elimina al reformular. Pasó en F3
   y F4 en la ejecución final, y en F2–F5 en `run1`.
2. **Información alterada o engañosa en preguntas sin respuesta (F6).**
   El agente dice que "el precio se detalla en la FAQ-061", pero esa ficha no
   contiene ningún precio. Además, escribió el correo de soporte como
   `support@parachutesa.gt`, cuando el real es `soporte@`. No inventó cifras.
3. **No avisa de una cita duplicada (R7).** La tool devolvió `ya_existia: true`
   con el mismo ID, pero la respuesta dice "✅ Cita registrada… ¡La cita está
   lista!", como si fuera nueva. Factuality lo detectó como contradicción.
4. **Latencia.** R2 (53.3 s) y F6 (20.9 s) superan los umbrales. En `run1`
   los superaron 8 casos (F1–F6, R2 y R7), y R1, que terminó en error, tardó
   63.6 s. La variación entre ejecuciones es grande; por ejemplo,
   F3 bajó de 50.1 s a 10.3 s.
5. **Comportamiento no determinista.** Entre `run1` y la ejecución final,
   varios casos cambiaron de resultado sin cambios en el agente:
   - **R1:** primero falló con `ModelBehaviorError` (ver hallazgo 6) y luego pasó.
   - **R2:** primero **no registró la cita** (preguntó "¿Deseas registrar…?"
     con todos los datos ya dados) y luego sí lo hizo.
   - **F1:** primero inventó que los 100 kg eran "el peso total de la aeronave
     con equipaje" y luego respondió correctamente.

   Una sola ejecución no basta para afirmar que un caso "funciona".
6. **Formato *harmony* filtrado (gpt-oss-20b en NIM).** En `run1` el modelo
   pidió la tool `gestionar_operaciones<|channel|>commentary`. Cuando ocurre en
   el Supervisor, corta el run (R1); dentro de un sub-agente, el SDK devuelve
   el error y el Supervisor reintenta (R7). Es un problema de esa combinación
   de modelo y proveedor; ver la limitación 1.
7. **Alucinación de fechas y umbrales (R8, `run1`).** Con clima real se pidió
   el 2026-10-02 y el agente habló del "24 de octubre". También inventó un
   umbral de lluvia ("máx. 1 mm"); la regla real es que cualquier valor mayor
   que 0 está prohibido. Esto motivó el check `check_dates`; en la ejecución
   final la fecha fue correcta.
8. **La búsqueda no filtra preguntas fuera del corpus.** Con
   `SEARCH_MIN_SIMILARITY=0.35`, "¿Ofrecen clases de surf?" recupera 5 FAQs
   irrelevantes (similitud 0.42–0.45), así que `sin_evidencia` nunca se activa.
   El agente igual respondió correctamente que no hay información (F7).
9. **Defectos del corpus (datos de la HT4/HT5).**
   - FAQ-039 (ataques de pánico) tiene la respuesta de edad mínima.
   - FAQ-103 (viento que suspende operaciones) tiene la de velocidad en caída libre.
   - FAQ-023 dice "18 años cumplidos" y a la vez que pueden participar menores
     de 16 y 17 años, e incluye la palabra en inglés "presenting".

Comportamientos correctos verificados:
- Con clima prohibido nunca se llamó a `calendarizar_cita` ni se escribió en la
  base (R3, R4, R8).
- Con datos incompletos se pidieron nombre y hora sin registrar (R6).
- Fuera del horizonte se explicó el límite de 16 días (R5).
- No se inventó información fuera del corpus (F7).
- Toda cita creada pasó antes por la consulta del clima para la misma fecha.

## 9. Limitaciones

1. **Modelo sustituto.** La HT5 se diseñó para el modelo predeterminado de
   OpenAI (`OPENAI_API_KEY`). Como el equipo no tenía esa clave, se evaluó con
   `openai/gpt-oss-20b` en NVIDIA NIM vía Chat Completions. Los resultados
   describen **esta arquitectura con ese modelo**: los hallazgos 5 y 6 pueden
   no repetirse con otro modelo. Para cambiarlo, edita `agent_model` en
   `promptfooconfig.yaml`.
2. **Una ejecución por caso.** No se usó `--repeat`; los resultados
   individuales pueden variar (hallazgo 5). Para tasas más confiables:
   `npm run eval -- --repeat 3`, que triplica tiempo y costo.
3. **El grader también es un LLM.** Puede equivocarse. Por eso cada caso
   combina factuality con checks deterministas, y su razonamiento está en el
   reporte.
4. **Los checks de afirmaciones son léxicos.** `check_claims` busca verbos
   como "confirmada", "registrada" o "agendada", y trata negaciones y
   condicionales. No detecta afirmaciones con otras palabras; por ejemplo, en
   R8 final el agente escribió que "el salto **prohibido** está **programado**",
   una frase ambigua que el check no marca.
5. **Escenarios climáticos.** En R1–R4, R6 y R7 la lectura climática es fija;
   la evaluación de esos datos sí es la real del sistema. Solo R5 (validación
   de fecha) y R8 usan el camino real de Open-Meteo, y el resultado de R8
   depende del pronóstico del día.
6. **Latencia dependiente del proveedor.** Se midió contra el nivel gratuito
   de NIM, con variación alta entre ejecuciones. Los umbrales son propios de
   este eval.

## 10. Decisiones del harness y su motivo

Ninguna modifica el agente ni la lógica de reservas.

| Decisión | Motivo |
|---|---|
| Modelo inyectado con `RunConfig` | No había clave de OpenAI. `RunConfig` se propaga a los sub-agentes sin tocar su código |
| Event loop persistente en el provider | El SDK reutiliza un cliente HTTP global ligado al loop; con `asyncio.run` por caso, el segundo caso fallaba con "Event loop is closed" |
| Embeddings cargados en la primera llamada | Promptfoo exige que el worker Python esté listo en 30 s (valor fijo) y cargar torch al importar tardaba unos 37 s |
| `database_url` en la config del provider | El bloque `env:` de Promptfoo no llega al worker Python |
| `maxConcurrency: 1` | Los escenarios climáticos reemplazan una función del proceso, y así la latencia no se mezcla entre casos |
| Grader con `max_tokens: 16384` | Con 4096, `glm-5.3` agotaba el presupuesto razonando y no emitía veredicto (afectó a 4 casos de `run1`) |
| Regex de citas acepta `FAQ‑021` (U+2011) | El modelo escribe guiones no separables; es la misma cita |

## Historial de ejecuciones

- **Corrida descartada (no conservada).** El equipo se suspendió a mitad de la
  ejecución y las conexiones quedaron rotas; sus latencias no eran válidas.
- **`reports/run1/` (2026-09-30):** 5 pasan, 9 fallan, 1 error. Tenía dos
  defectos del harness:
  - el grader sin tokens suficientes, que dio "No output" en R2, R3 y R7 y un
    veredicto truncado en F5 (el grader había concluido la categoría B, que
    aprueba);
  - un falso positivo de `check_claims` en R2, por tomar "Una vez confirmado…"
    como afirmación.

  Se corrigieron con pruebas que reproducen esos textos y se agregó
  `check_dates`. Ni datasets, ni referencias, ni umbrales se modificaron.
- **`reports/` (final, 2026-10-01):** la ejecución entregable descrita arriba.
