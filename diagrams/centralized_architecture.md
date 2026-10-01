# Diagrama — Arquitectura centralizada

```mermaid
graph TD
    U["Usuario"] --> M["Manager Central<br/>centralized/manager.py"]

    M -->|"as_tool: responder_faq"| F["Agente de FAQs"]
    M -->|"as_tool: consultar_clima"| W["Agente de Clima"]
    M -->|"as_tool: registrar_reserva<br/>solo después del clima"| B["Agente de Reservas"]

    W --> S["Servicio climático compartido<br/>shared/weather_service.py"]
    S --> C["Cliente Open-Meteo<br/>shared/open_meteo_client.py"]
    C --> API[("Open-Meteo API")]
    S --> E["Evaluador de umbrales<br/>shared/weather_evaluator.py"]

    classDef manager fill:#d8e9ff,stroke:#255c99,color:#111;
    classDef specialist fill:#e8f5e9,stroke:#2e7d32,color:#111;
    classDef shared fill:#fff3cd,stroke:#997404,color:#111;
    class M manager;
    class F,W,B specialist;
    class S,C,E shared;
```

El Manager Central conserva el control de la conversación. Los agentes
especializados se exponen mediante `Agent.as_tool()` y devuelven su resultado
al manager. La regla “consultar clima antes de reservar” reside en un solo
lugar: las instrucciones del manager.

FAQs y almacenamiento de reservas son implementaciones provisionales para que
el programa sea ejecutable; el Integrante 3 podrá sustituirlas por sus módulos
definitivos sin cambiar el cliente climático ni el evaluador.
