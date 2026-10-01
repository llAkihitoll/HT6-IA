> Borrador original del integrante 2. La respuesta consolidada tras integrar
> las tres arquitecturas está en [RESPUESTAS.md](RESPUESTAS.md). La regla de
> clima se garantiza ahora en el servicio compartido de reservas, también
> para handoffs, sin duplicarla en los prompts.

# Pregunta 1 — Integrante 2

**¿Qué arquitectura/arquitecturas resuelven mejor este problema? ¿Por qué?**

## Contexto del problema

Parachute S.A. necesita un sistema que (1) responda preguntas frecuentes,
(2) calendarice citas, y (3) antes de calendarizar, consulte el clima y
determine si las condiciones permiten el salto. El enunciado agrega una
restricción importante para esta comparación: la empresa **seguirá
incrementando los requerimientos funcionales**. Por eso, además de
resolver el problema actual, la arquitectura elegida debe facilitar
agregar nuevas capacidades sin reescribir lo que ya funciona.

Dos observaciones sobre el problema son relevantes para comparar las
arquitecturas:

- Existe una **regla de negocio transversal** que debe cumplirse sin
  excepción: nunca calendarizar sin haber consultado antes el clima. Esta
  regla debe imponerse sin importar por dónde entre la solicitud del
  usuario.
- Las capacidades actuales se agrupan naturalmente en dos familias:
  **informativa** (FAQs) y **operativa** (clima + reservas, con
  probabilidad alta de que crezca: por ejemplo, verificación de equipo,
  asignación de instructor, pagos, etc., mencionados como "más
  requerimientos" por el cliente).

## Nota metodológica

Esta respuesta distingue tres tipos de afirmación:

- **Observación de la implementación**: algo que efectivamente construí y
  verifiqué en la arquitectura jerárquica (la única que yo implementé).
- **Argumento teórico**: razonamiento sobre cómo se comportaría cada
  arquitectura, sin haberlo medido.
- **Resultado experimental**: **no incluyo ninguno** — no se realizaron
  mediciones de latencia, costo de tokens, ni pruebas de carga entre las
  tres arquitecturas. Cualquier lectura de "más rápido/lento" o
  "más caro/barato" entre arquitecturas en este documento es argumento
  teórico, no un dato medido.

Como al momento de escribir esta respuesta las arquitecturas centralizada
y descentralizada de Integrante 1 e Integrante 3 todavía no existían en
el repositorio, todo lo que digo sobre ellas es argumento teórico basado
en cómo las describe el enunciado y en la semántica documentada del SDK
de OpenAI Agents (en particular, la diferencia entre `as_tool()` y
`handoff` descrita en su propia documentación: con `as_tool()` el agente
que delega mantiene el control y recibe una respuesta; con `handoff` el
control de la conversación se transfiere por completo al nuevo agente).

## Comparación por dimensión

| Dimensión | Centralizada | Jerárquica | Descentralizada (handoffs) |
|---|---|---|---|
| Organización de responsabilidades | Un solo manager conoce y expone FAQs, clima y reservas al mismo nivel. | Dos niveles: Supervisor separa lo informativo de lo operativo; el Submanager agrupa clima y reservas. | Sin autoridad central; cada agente (FAQs, Clima, Reservas) es un par que puede transferir la conversación a otro. |
| Coordinación | Un punto único decide todo. | Coordinación distribuida en dos niveles; cada nivel decide solo dentro de su dominio. | No hay coordinador; la "coordinación" ocurre implícitamente en las instrucciones de cada agente sobre a quién transferir. |
| Comunicación | Manager ↔ herramientas (function tools), directo. | Supervisor ↔ Submanager ↔ Agentes especializados, vía `as_tool()` (con retorno de resultado). | Agente activo ↔ agente activo, vía `handoff` (con transferencia total de control, sin retorno automático). |
| Facilidad para agregar requerimientos | Baja a mediana: cada capacidad nueva se agrega al mismo manager, que crece sin límite natural. | Alta: una capacidad operativa nueva se agrega bajo el Submanager sin tocar el Supervisor ni las demás ramas *(observación de la implementación: agregar el Agente de Reservas no requirió modificar `supervisor.py`)*. | Mediana: se agrega un nuevo agente par, pero hay que decidir y mantener manualmente desde/hacia qué agentes puede recibir o hacer handoff. |
| Mantenimiento | El prompt/instrucciones del manager mezcla reglas de dominios distintos (FAQs, clima, reservas) en un solo lugar. | Cada nivel tiene instrucciones acotadas a su dominio; la regla "consultar clima antes de reservar" vive en un solo archivo (`operations_manager.py`) *(observación de la implementación)*. | Las reglas transversales deben repetirse o coordinarse entre los agentes pares involucrados, porque no hay un lugar único "por encima" de ellos. |
| Escalabilidad (nº de capacidades) | Se degrada al crecer: un manager con demasiadas herramientas es más difícil de instruir de forma confiable. | Se degrada más lentamente: el árbol puede crecer agregando ramas/submanagers adicionales. | Escala en número de agentes, pero la complejidad de las reglas de transferencia entre pares crece de forma más difícil de predecir. |
| Control sobre el flujo | Alto y explícito (todo pasa por el manager). | Alto y explícito, pero repartido en dos niveles. | Bajo: el control de la conversación se transfiere por completo a quien recibe el handoff; recuperarlo requiere otro handoff. |
| Complejidad | Baja para pocas capacidades. | Media (hay una capa adicional de indirección: Supervisor → Submanager → Agente). | Media-alta: la complejidad se traslada a diseñar correctamente la red de transferencias entre pares. |
| Dependencia entre agentes | Todos dependen del manager central (single point of coordination). | Dependencia jerárquica y acotada: un agente hijo no necesita saber nada de sus hermanos. | Dependencia lateral: cada agente debe "saber" a qué otros agentes puede transferir, acoplando a los pares entre sí. |
| Adecuación a la regla "consultar clima antes de reservar" | Fácil de imponer: el manager la aplica antes de invocar la herramienta de reservas. | Fácil de imponer y bien localizada: el Submanager la aplica una sola vez, para toda solicitud operativa presente y futura. | Difícil de imponer de forma centralizada: como el control se transfiere entre pares, la regla debe repetirse en las instrucciones de cada agente que pueda llegar a ofrecer una reserva. |

## Análisis

**Arquitectura centralizada.** Es la más simple de razonar con pocas
capacidades, y resuelve el problema actual sin dificultad: un manager con
tres herramientas (FAQs, clima, reservas) puede aplicar la regla de
consultar el clima antes de reservar sin mayor esfuerzo. El riesgo,
dado que el cliente **ya avisó que seguirá pidiendo más funcionalidad**,
es que todo ese crecimiento se acumule en las instrucciones y el conjunto
de herramientas de un único agente, mezclando dominios que no se
relacionan entre sí (una FAQ sobre política de cancelación no tiene nada
que ver con la lógica de asignar un instructor). Esto es un argumento
teórico: no hay una medición de qué tan mal escala en la práctica, pero
es una consecuencia directa de cómo describe el enunciado el crecimiento
esperado de requerimientos.

**Arquitectura jerárquica.** Es la que implementé, y la que mejor refleja
la estructura natural del dominio: separa lo informativo (FAQs) de lo
operativo (clima + reservas), y dentro de lo operativo aplica la regla
transversal en un único punto (`operations_manager.py`). Puedo afirmar
directamente, por haberlo construido, que agregar el Agente de Reservas
al Submanager no requirió tocar el Supervisor General, y que el
Evaluador Climático (`shared/weather_evaluator.py`) quedó totalmente
desacoplado de la orquestación — es una función pura reutilizable por
cualquier arquitectura. El costo es una capa adicional de indirección
(cada solicitud operativa pasa por Supervisor → Submanager → Agente
especializado), lo cual en teoría implica más "saltos" de razonamiento
del modelo que una llamada directa del manager centralizado — de nuevo,
un argumento teórico, no una medición de latencia real.

**Arquitectura descentralizada (handoffs).** Es la que, en teoría, tiene
más dificultad para este problema específico, precisamente por la regla
transversal "siempre consultar el clima antes de reservar". Con
`handoff`, el control de la conversación se transfiere por completo al
agente receptor (según la documentación del propio SDK); no hay un
punto que reciba automáticamente el resultado de "Clima" antes de decidir
si delega a "Reservas". Para que la regla se cumpla, cada agente que
pudiera terminar ofreciendo una reserva tendría que incluir esa
verificación en sus propias instrucciones, duplicando lógica de negocio
en varios lugares en vez de centralizarla. Esta arquitectura puede tener
otras ventajas (por ejemplo, conversaciones más fluidas cuando el usuario
cambia de tema libremente, sin un "jefe" que reconduzca cada mensaje),
pero esas ventajas no son las más relevantes para el problema concreto de
Parachute S.A., donde lo crítico es garantizar una secuencia de
verificación antes de una acción irreversible (agendar un salto).

## Conclusión

Para el problema específico de Parachute S.A. — un conjunto de
capacidades que crecerá con el tiempo, agrupables en informativas y
operativas, con al menos una regla de negocio transversal que debe
cumplirse siempre — la **arquitectura jerárquica es la que mejor se
adapta**: aísla el crecimiento futuro de requerimientos operativos bajo
un submanager sin inflar las instrucciones del nivel superior, y ofrece
un único lugar natural para imponer reglas de negocio que atraviesan
varias capacidades (clima + reservas), sin sacrificar la separación de
responsabilidades.

La arquitectura **centralizada** es una alternativa razonable mientras el
número de capacidades sea pequeño (como ocurre hoy), y probablemente sea
la más simple de implementar y depurar en ese escenario — pero, según el
propio enunciado de que la funcionalidad seguirá creciendo, es la que
previsiblemente necesitará más refactorización a futuro (esto es una
predicción teórica, no algo que se haya observado directamente, ya que no
formé parte de la implementación centralizada).

La arquitectura **descentralizada** es la menos adecuada para esta regla
de negocio transversal específica, por cómo transfiere el control de la
conversación entre agentes pares en lugar de mantenerlo en un coordinador
que pueda secuenciar verificaciones antes de una acción crítica. Esto no
significa que sea una mala arquitectura en general — solo que no es la
mejor opción para *este* problema, dado *este* requisito de negocio en
particular.
