# HT5 — Sistemas multiagentes para Parachute S.A.

Tres programas resuelven FAQs, consulta climática y registro de citas con las
mismas integraciones. Las diferencias están en la orquestación.

| Arquitectura | Programa | Coordinación |
|---|---|---|
| Centralizada | `python -m centralized.main` | Manager con especialistas como herramientas |
| Jerárquica | `python -m hierarchical.main` | Supervisor → submanager → especialistas |
| Descentralizada | `python -m decentralized.main` | FAQs ↔ clima ↔ reservas mediante handoffs |

La parte 3 reemplaza las FAQs y reservas provisionales de las otras dos
arquitecturas por búsqueda semántica y persistencia compartidas.

## Instalación

Python 3.10 o superior y Docker con Compose para PostgreSQL.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copiar `.env.example` a `.env` (`cp` en macOS/Linux o `Copy-Item` en PowerShell).
Configurar `OPENAI_API_KEY`. `OPENAI_MODEL` permite elegir el modelo de la CLI
descentralizada; vacío conserva el predeterminado del SDK.

```bash
docker compose up -d --wait
python -m shared.faq_store.load_data
python -m decentralized.main
```

El cargador adapta el Lab 4: 120 FAQs, seis categorías, embeddings locales
`all-MiniLM-L6-v2` de 384 dimensiones, PostgreSQL + pgvector y carga idempotente.
La primera carga necesita descargar el modelo. La búsqueda usa distancia coseno,
umbral configurable y devuelve evidencia con `faq_id`. No hay respuestas fijas
ni fallback al conocimiento general si falla la base.

El contenedor del Lab 5 usa el puerto **5433** para no interferir con el Lab 4.
Si ya tienes la base del Lab 4 cargada, puedes apuntar `DATABASE_URL` a esa base
y omitir levantar/cargar otra. Las reservas van a `BOOKINGS_DB` (SQLite local),
independiente de PostgreSQL. `docker compose down` detiene la base sin borrar
el volumen.

## Comportamiento

- Open-Meteo consulta las coordenadas **14.013722, -90.771611** mediante `daily`:
  temperatura media, precipitación acumulada y máximos de viento, ráfagas y nubes.
- Horizonte: **hoy hasta hoy + 15 días**, 16 fechas en `America/Guatemala`.
- `shared/weather_evaluator.py` conserva los umbrales del integrante 2.
- `shared/bookings.py` vuelve a consultar y evaluar el clima antes de escribir.
  El modelo no puede proporcionar un veredicto para omitir esta comprobación.
- Ideal: cita `confirmada`. Marginal: `pendiente_revision`, conservando las
  restricciones (incluido tándem experimentado). Prohibido/error: no se guarda.
  La política de dejar marginales pendientes es una decisión de implementación.
- Fecha, nombre y hora deben acordarse con el usuario. La hora es de Guatemala;
  el pronóstico es diario. No se implementan cupos, pagos, cancelación ni
  reprogramación. El registro es local, no un evento de Google Calendar.
- La combinación fecha + hora + nombre normalizado evita duplicados, incluso
  con llamadas concurrentes o reinicios. Personas homónimas en la misma hora
  no se distinguen en esta versión académica.
- La CLI descentralizada conserva historial y agente activo entre mensajes,
  muestra cada handoff y limita a 12 turnos de modelo por mensaje. `salir`,
  `Bye`, Ctrl+C y EOF terminan la sesión. El historial no persiste al cerrar.

## Validación

```bash
python -m pytest -q
```

La suite valida umbrales, fechas, datos inválidos, corpus, SQL de búsqueda,
reservas persistentes/concurrentes y handoffs mediante el Runner real del SDK
con un modelo simulado. No requiere claves ni servicios externos.

En esta entrega se verificó además una consulta real a Open-Meteo. La sesión
con LLM y la búsqueda contra PostgreSQL real no se verificaron en este entorno:
no había API key configurada ni Docker disponible. Las pruebas simuladas no
miden calidad de respuestas, latencia ni costo real del modelo.

En macOS, si Python no encuentra certificados TLS, configura su almacén de
certificados. Por ejemplo, para una terminal con el entorno activado:

```bash
export SSL_CERT_FILE="$(python -m certifi)"
```

No deshabilites la validación HTTPS. Este ajuste solo fue necesario en el
Python local usado para verificar la consulta real.

## Documentación

- [Parte 3: ejecución, pruebas e integración](docs/EJECUCION_INTEGRANTE3.md)
- [Diagrama descentralizado](diagrams/decentralized_architecture.md)
- [Diagrama centralizado](diagrams/centralized_architecture.md)
- [Diagrama jerárquico](diagrams/hierarchical_architecture.md)
- [Respuestas consolidadas](docs/RESPUESTAS.md)
- [PDF de entrega](output/pdf/respuestas_lab5.pdf)


