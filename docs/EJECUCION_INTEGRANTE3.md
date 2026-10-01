# Parte 3 — Descentralizada, FAQs y reservas

## Qué se agregó

- `decentralized/agents.py`: tres especialistas pares, handoffs explícitos y
  trazas en consola. FAQs es el punto de entrada, no un supervisor.
- `decentralized/main.py`: historial mediante `to_input_list()` y continuidad
  del agente mediante `last_agent`, entre mensajes del mismo usuario.
- `shared/faqs.py` y `shared/faq_store/`: adaptación del Lab 4, manteniendo el
  corpus, parser, carga idempotente, embeddings locales y consulta pgvector.
- `shared/bookings.py`: SQLite persistente, unicidad transaccional y
  comprobación de clima dentro del servicio que escribe la cita.
- `shared/agent_tools.py` y `shared/specialists.py`: integraciones comunes;
  centralizada y jerárquica ya las usan manteniendo sus managers.
- Diagrama y respuestas en Markdown/PDF, con script reproducible del PDF.

## Arranque

Seguir la instalación del README, levantar PostgreSQL y cargar el corpus.
Ejecutar desde la raíz del repositorio:

```bash
python -m decentralized.main
```

Completar la fecha de los ejemplos con un día futuro dentro del pronóstico:

1. «¿Dónde se ubica la zona de salto?» → consultar FAQs y citar identificadores.
2. «Quiero reservar para mañana» → handoff FAQs → Clima, consulta real.
3. Si el clima lo permite: «Me llamo Ana, a las 09:00» → Reservas recopila los
   datos faltantes y guarda. Reportar ID y estado devueltos por la herramienta.
4. Repetir exactamente la reserva → mismo ID, `ya_existia=true`, sin duplicado.
5. «¿Cuál es la política de cancelación?» → volver a FAQs mediante handoff.
6. Pedir una fecha a un mes → explicar que está fuera del horizonte.
7. Escribir `Bye` → finalizar.

No se puede garantizar un día ideal con el clima real. Para demostrar todos
los estados sin depender del pronóstico, ejecutar las pruebas automatizadas.

## Pruebas

```bash
python -m pytest -q
python -m pytest tests/test_decentralized.py tests/test_bookings.py -q
```

Los tests de handoffs ejecutan el Runner del SDK, las transferencias y las
herramientas reales; sustituyen solo las respuestas del modelo y las fronteras
externas (API meteorológica y consulta de FAQs). La escritura SQLite sí es real
en directorios temporales. Se prueban continuidad de sesión, consulta de FAQs,
error de base, ausencia de evidencia, ciclo de handoffs y guardado tras consulta.

Las pruebas de búsqueda simulan filas SQL y embeddings; no demuestran por sí
solas calidad semántica. Para validarla en la instalación del equipo:

```bash
python -m shared.faq_store.load_data
python -c "from shared.faqs import search_faqs; print(search_faqs('¿Dónde se ubica la zona de salto?'))"
```

Volver a ejecutar el cargador debe conservar 120 filas. Probar también una
paráfrasis y una pregunta ajena al corpus; ajustar el umbral con ejemplos
representativos si hace falta.

## Acuerdos y límites

- Las reglas de umbrales siguen en el evaluador del integrante 2.
- El servicio de reservas repite la consulta por seguridad aunque el agente
  Clima ya la haya hecho. No confía en texto del LLM ni en un estado suministrado.
- Marginal siempre queda pendiente de revisión humana. No se confirma mediante
  una simple afirmación del usuario de que tiene experiencia.
- Reintentar no cambia una cita existente ni implica reprogramarla. Un pronóstico
  marginal posterior exige revisión aunque la cita original fuera confirmada.
  Si se vuelve prohibido, el reintento es rechazado y la fila original se conserva;
  no se ofrece un sistema automático de cancelaciones ni de monitorización.
- Se valida el intervalo de 16 fechas contando hoy, el reloj de Guatemala y
  valores climáticos finitos/no negativos (excepto temperaturas negativas).
- La captura de datos y la decisión de usar herramientas dependen del modelo;
  los límites meteorológicos y la persistencia se imponen en código.
- No se crearon ni publicaron reservas reales durante las pruebas.

## Resultado de la verificación local

La suite completa pasa con el SDK `openai-agents 0.22.3`. Open-Meteo respondió
para 2026-09-19 con viento 16.7 km/h, ráfagas 39.2 km/h, lluvia 8.9 mm,
nubes 100% y temperatura 27.8 °C. El evaluador devolvió PROHIBIDO; se consultó
sin registrar ninguna cita. Es una observación puntual, no datos de demostración
fijos para futuras ejecuciones.

No se ejecutó una conversación con el proveedor LLM ni la base PostgreSQL real
en este entorno, por ausencia de API key y servicio Docker. Queda documentado
cómo verificarlos en la instalación del equipo.

## Regenerar el informe

```bash
python -m pip install reportlab
python scripts/build_report.py
```

Salida: `output/pdf/respuestas_lab5.pdf`. El diagrama Markdown es editable y
se renderiza directamente en GitHub.
