# Arquitectura descentralizada — Integrante 3

```mermaid
flowchart TB
    U[Usuario / CLI con historial] -->|Primer turno| F[Agente FAQs]
    F <-->|handoff| C[Agente Clima]
    C <-->|handoff| R[Agente Reservas]
    R -->|handoff| F
    F -.->|buscar_faq| Q[shared.faqs]
    Q --> PG[(PostgreSQL + pgvector / FAQs Lab 4)]
    C -.->|consultar_clima| W[weather_service]
    W --> O[Open-Meteo daily]
    W --> E[weather_evaluator]
    R -.->|calendarizar_cita| B[shared.bookings]
    B -->|Reconsulta antes de guardar| O
    B -->|Aplica los mismos umbrales| E
    B -->|Ideal: confirmada / marginal: pendiente| DB[(SQLite persistente)]
```

Las flechas `handoff` transfieren el control entre agentes pares. Las flechas
punteadas son llamadas a funciones, no a otros agentes. No existe manager ni
uso de `as_tool()` en esta arquitectura. Tras el primer turno, la CLI continúa
con `last_agent` y el historial; cualquier agente activo puede contestar al usuario.

La condición climática se vuelve a verificar en `shared.bookings` antes de
escribir, independientemente de la ruta de handoffs. Prohibido o error no crea
una cita. El límite de 12 turnos del Runner acota ciclos de transferencias.

![Diagrama de agentes e integraciones](decentralized_architecture.png)
