> Nota de integración: las FAQs y reservas provisionales fueron sustituidas
> por los módulos compartidos del integrante 3. Consulta el README actual
> para instalar PostgreSQL y cargar el corpus antes de ejecutar esta arquitectura.

# Ejecución — Integrante 1

Responsable: **Juan Jose Rivas Alvarez — carnet 24856**.

Esta entrega incluye la arquitectura centralizada y la integración real y
reutilizable con Open-Meteo.

## Preparación

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Agrega una API key válida de OpenAI en `.env`. Open-Meteo no necesita API key
para este uso académico.

## Ejecutar la arquitectura centralizada

```bash
python -m centralized.main
```

Ejemplos para la CLI:

- `¿Cuál es la edad mínima para saltar?`
- `¿Es seguro saltar el 2026-09-22?`
- `Quiero reservar el 2026-09-22 a nombre de Ana López.`

Usa una fecha que esté entre hoy y los siguientes 16 días. Para una reserva,
el manager debe consultar primero el clima y bloquear condiciones prohibidas.

## Ejecutar pruebas

Todas las pruebas:

```bash
python -m pytest -q
```

Solo la integración climática:

```bash
python -m unittest tests.test_open_meteo_client -v
```

Las pruebas usan inyección de una respuesta simulada: no consumen Open-Meteo,
no necesitan conexión a internet y comprueban fechas, parámetros, mapeo de las
cinco variables y respuestas incompletas.

## Mapeo de variables

- `temperature_2m_mean` → `temperature_2m`
- `precipitation_sum` → `precipitation`
- `cloud_cover_max` → `cloud_cover`
- `wind_speed_10m_max` → `wind_speed_10m`
- `wind_gusts_10m_max` → `wind_gust_10m`

Los máximos diarios son deliberadamente conservadores para las variables de
seguridad. El contrato interno `WeatherReading` evita que los agentes dependan
directamente del formato de Open-Meteo.
