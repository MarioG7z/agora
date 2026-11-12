# Hallazgos de las corridas con modelo real

**Fecha:** 2026-11-11, actualizado el 2026-11-12.
**Alcance:** trece ejecuciones de AGORA con dos modelos reales sobre la tarea de ejemplo. Recoge qué
falló, la causa comprobada o la hipótesis, qué se cambió y qué queda por decidir.

## 1. Condiciones

| Dato | Valor |
|---|---|
| Modelos | `mistralai/ministral-8b-2512` (`real-1` a `real-9`) y `qwen/qwen3-coder-30b-a3b-instruct` (`real-10` a `real-13`), vía OpenRouter, el mismo para los cuatro expertos en cada ejecución |
| Tarea | "Una API para consultar un inventario de productos y filtrarlos por categoria" |
| Herramientas | Sin búsqueda web: la fase de Planning todavía no usa Tavily |
| Auditor | Solo reglas en código (reglas C, sección 8.2 del diseño) |

Las duraciones y conteos de este documento salen del registro de eventos (`logs/<ejecución>.jsonl`)
y del tablero guardado en SQLite (`workspace/agora.db`).

| Ejecución | Duración | Resultado |
|---|---|---|
| `real-1` | 32 s | Falla en Planning, sin causa visible |
| `real-2` | 41 s | Falla en Planning, con causa visible |
| `real-3` | 423 s | Pasa Planning, PRD y Spec; falla en Implementation |
| `real-4` | 202 s | Pasa Planning y PRD; la Spec falla tras 3 rechazos |
| `real-5` | — | Falla en Planning: el modelo vuelve a copiar el esquema |
| `real-6` | 85 s | Pasa Planning y PRD; la Spec falla tras 3 rechazos |
| `real-7` | 84 s | Pasa Planning y PRD; la Spec falla tras 3 rechazos |
| `real-8` | 75 s | Pasa Planning y PRD; la Spec falla tras 3 rechazos |
| `real-9` | 161 s | Pasa hasta la Spec; Implementation falla sin resultados de pruebas |
| `real-10` | 99 s | Pasa hasta la Spec; Implementation falla sin archivos de pruebas |
| `real-11` | 85 s | Pasa hasta la Spec; Implementation falla sin archivos de pruebas |
| `real-12` | 154 s | Pasa hasta la Spec; Implementation falla tras 3 rechazos |
| `real-13` | 154 s | **Ejecución completa**, con un rechazo de la Spec y dos de Implementation |

## 2. Error sin causa (`real-1`)

**Observado.** El agente de Planning agotó sus 3 intentos de formato y el error solo decía
"failed after 3 attempts". No se guardó qué respondió el modelo ni qué falló en la validación.

**Causa comprobada.** `SchemaValidationError` no incluía el último error de validación.

**Cambio.** El error ahora incluye el último error de Pydantic. Con eso, `real-2` mostró la causa.

## 3. Respuesta envuelta en markdown que imita el esquema (`real-2`)

**Observado.** El texto del modelo empezaba con un bloque de markdown (` ```json `) y, dentro, con
la clave `"$defs"`, que pertenece al esquema JSON enviado en el prompt y no al `ResearchBrief`.

**Causa comprobada.** Dos comportamientos del modelo: envolver el JSON en markdown e imitar la
estructura técnica del esquema en lugar de llenarlo.

**Cambio.** El cliente pide al proveedor salida JSON con `response_format: {"type": "json_object"}`.
Es una restricción en código, no un cambio de prompt. En `real-3`, Planning y PRD pasaron al primer
intento: el cambio resolvió los dos comportamientos.

## 4. Re-ejecución con el veredicto (`real-3`)

**Observado.** El auditor rechazó la primera Spec porque `REQ-2` no tenía interfaz. El segundo
intento, que recibió el veredicto en su entrada, pasó.

Es la primera evidencia con un modelo real de que el ciclo de auditoría y re-ejecución corrige un
defecto concreto sin intervención humana.

## 5. Alcance inflado desde la investigación (`real-3`)

**Observado.** El tamaño de los artefactos creció en cada fase:

| Fase | Tamaño del artefacto aprobado |
|---|---|
| Planning | 10 pedidos (`ASK`) y 10 hallazgos |
| PRD | 10 requisitos |
| Spec | 46 archivos en TypeScript y markdown, 33 pruebas planeadas |
| Implementation | 29 archivos escritos, ningún resultado de prueba |

El Desarrollador no logró escribir los 46 archivos en una sola respuesta, ni pruebas en Python. El
auditor lo rechazó tres veces con la lista exacta de archivos y pruebas faltantes, y la tarea
terminó en `fallida` en lugar de entregar un resultado incompleto.

**Causa.** Hay dos, de distinto nivel:

- **Comprobada:** el prompt del Arquitecto no exige Python ni una solución mínima; solo el del
  Desarrollador lo hace. El Arquitecto eligió TypeScript.
- **Hipótesis:** el defecto nace en Planning. Una petición de una línea produjo 10 pedidos, y cada
  fase siguiente cubrió fielmente lo que recibió. Es el caso de la sección 7.3 del diseño: la falla
  se detectó en Implementation, pero su origen está antes.

**Hipótesis adicional.** Sin búsqueda web, las fuentes de los 10 hallazgos no se recuperaron en la
ejecución; es probable que el modelo las haya inventado. La regla C de fuentes recuperadas, aún no
implementada, las rechazaría.

## 6. Reintentos de formato invisibles

**Observado.** Los reintentos internos del agente (hasta 3 por fase, sección 7.1) no emiten eventos.
Por eso no se puede contar con exactitud cuántas llamadas al modelo hizo `real-3`: el registro solo
asegura un mínimo de 7, una por cada intento de fase.

**Causa comprobada.** El agente no tiene acceso al flujo de eventos; solo el orquestador emite.

## 7. La regla de archivos Python (`real-4`)

**Cambio.** Regla C nueva en el auditor: todos los archivos de la Spec deben terminar en `.py`
(decisión abierta 1 de la versión anterior de este documento).

**Observado.** La falla se adelantó de Implementation a la Spec, que es donde se rechaza y donde
cuesta menos: la Implementation ya no se ejecutó.

| Intento de Spec | Archivos | Extensiones | Motivo del rechazo |
|---|---|---|---|
| 1 | 33 | `js`, `yaml`, `yml` | 33 archivos que no son Python |
| 2 | 22 | `py`, `yaml`, `yml` | Solo quedan los de Docker y Kubernetes |
| 3 | 33 | `py`, `yaml`, `yml` | Además, 27 nombres de servicios en `covers` que no son requisitos |

El modelo corrigió casi todo con el veredicto del primer rechazo, pero el alcance siguió inflado.

**Causa, ahora con evidencia.** Los 7 pedidos de Planning no son pedidos del usuario sino preguntas
de investigación, por ejemplo "¿Cuáles son los estándares y buenas prácticas para el diseño…?" o
"¿Qué herramientas de monitoreo y métricas son esenciales…?". El investigador confundió *qué pidió
el usuario* con *qué conviene investigar*. Cada fase siguiente cubrió fielmente esas preguntas: de
ahí salen la caché, el monitoreo, Kubernetes y el resto. Esto confirma la hipótesis del hallazgo 5:
el defecto nace en Planning.

## 8. Pedidos del usuario y forma de la respuesta (`real-5` a `real-7`)

**Cambio 1.** El prompt del investigador precisa que un pedido es solo algo que el usuario pidió de
forma explícita, nunca una pregunta de investigación ni una funcionalidad añadida.

**Observado en `real-5`.** La ejecución falló en Planning porque el modelo volvió a responder con la
estructura del esquema (`$defs`, `properties`) en lugar de llenarla. El problema del hallazgo 3 no
estaba resuelto: seguía latente y no apareció en `real-3` ni en `real-4`.

**Consecuencia de método.** El modelo varía entre llamadas, así que una sola ejecución no permite
atribuir un efecto a un cambio. Desde aquí, cada cambio se evalúa con al menos dos ejecuciones.

**Cambio 2.** El prompt ya no incluye el esquema JSON técnico, sino la forma de la respuesta, por
ejemplo `{"asks": [{"id": "string", "description": "string"}]}`, generada a partir del contrato.

**Observado en `real-6` y `real-7`.**

| Aspecto | `real-6` | `real-7` |
|---|---|---|
| Planning y PRD | Aprobados al primer intento | Aprobados al primer intento |
| Pedidos | 7 | 8 |
| Pedidos que la tarea sí contiene | 2 (consultar y filtrar) | 2 (consultar y filtrar) |
| Lenguaje de la primera Spec | TypeScript | PHP |
| Último rechazo de la Spec | `openapi.yaml`, `ProductSchema.json` y `.xml` | `swagger.yaml` |

- Ninguna de las dos copió el esquema: el cambio 2 resolvió la causa de fondo del hallazgo 3.
- Los pedidos ya no son preguntas de investigación, pero se siguen añadiendo funcionalidades que la
  tarea no menciona, como autenticación, paginación o XML. El cambio 1 corrigió el tipo de pedido,
  no el alcance.
- En las tres ejecuciones que llegaron a la Spec, el Arquitecto eligió primero un lenguaje distinto
  de Python. La regla de archivos Python lo detectó siempre, y con el veredicto el modelo convergió a
  Python, pero insistió en archivos de documentación (`yaml`, `json`) hasta agotar los intentos.

## 9. Arquitecto en Python, evidencia de pytest y otro modelo (`real-8` a `real-13`)

**Cambio 1.** El prompt del Arquitecto pide un proyecto mínimo, solo con archivos `.py`, sin
documentación, configuración ni despliegue.

**Observado.** En `real-8` la Spec siguió insistiendo en `openapi.yaml` y `product_schema.json`. En
`real-9` pasó al primer intento por primera vez, pero Implementation no produjo ningún resultado:
el código importaba Flask, que no está instalado, y pytest no pudo cargar las pruebas. El veredicto
solo decía qué pruebas no se ejecutaron, sin la causa, y el Desarrollador repitió el error tres
veces.

**Cambio 2.** El `Implementation` lleva las líneas de error de pytest (`E ...`), y el auditor las
incluye como evidencia de la regla "pytest reports no errors".

**Cambio 3.** Modelo `qwen/qwen3-coder-30b-a3b-instruct`: variante sin razonamiento, con soporte
de `response_format` y especializada en código. Según el catálogo de OpenRouter consultado el
2026-11-12, cuesta 0.15 USD por millón de tokens de entrada (igual que Ministral) y 0.60 de salida
(0.15 en Ministral).

**Observado en `real-10` y `real-11`.** Planning produjo exactamente los 2 pedidos de la tarea
(consultar y filtrar) y el PRD, 2 requisitos: el alcance inflado de las ejecuciones anteriores
dependía sobre todo del modelo pequeño. Pero la Spec planeó 4 y 5 pruebas sin ningún archivo bajo
`tests/`; el Desarrollador escribió solo los archivos listados y pytest no encontró pruebas. Ninguna
regla lo detectó en la Spec.

**Cambio 4.** Regla C nueva en la Spec: si hay pruebas planeadas, debe haber al menos un archivo
bajo `tests/`.

**Observado en `real-12` y `real-13`.**

- `real-13` es la primera ejecución completa con un modelo real. La regla nueva rechazó la primera
  Spec, el segundo intento la corrigió, e Implementation pasó al tercer intento después de que el
  veredicto mostró `No module named 'flask'`. Al repetir pytest sobre el código generado pasan 12
  pruebas, entre ellas las 7 planeadas en la Spec.
- En `real-12` el Desarrollador quitó Flask tras el primer veredicto, falló por errores de tipo en el
  segundo y volvió a Flask en el tercero. Cada reintento recibe solo el último veredicto, así que el
  modelo puede oscilar entre errores ya corregidos.

## 10. Decisiones

**Tomadas**

1. El error de esquema incluye el último error de validación.
2. El cliente de OpenRouter pide salida JSON con `response_format`.
3. Regla C en el auditor: todos los archivos de la Spec deben ser Python (`.py`).
4. El prompt del investigador define un pedido como algo que el usuario pidió de forma explícita.
5. El prompt muestra la forma de la respuesta en lugar del esquema JSON técnico.
6. El prompt del Arquitecto pide un proyecto mínimo, solo en Python.
7. El veredicto de Implementation incluye las líneas de error de pytest.
8. Regla C: la Spec con pruebas planeadas debe tener un archivo bajo `tests/`.

**Abiertas**

1. Una regla L (juez con modelo, sección 8.4 del diseño) que compruebe que cada pedido aparece en la
   tarea original. Las funcionalidades añadidas no se pueden detectar con una regla en código,
   porque requieren comparar significados.
2. Limitar en Planning el número de pedidos, o hacer que el auditor advierta cuando una petición
   corta produce muchos pedidos.
3. Registrar cada llamada al modelo como evento, con sus tokens y costo, para medir el costo de una
   ejecución (criterio de B8).
4. Pasar al reintento el historial de veredictos de la tarea, no solo el último, para evitar que
   el modelo oscile entre errores ya corregidos (`real-12`).
5. Elegir el modelo por fase: con la evidencia de este documento, `qwen3-coder` mantiene el alcance
   y escribe código que pasa; `ministral-8b` infla el alcance desde Planning.

Los cambios abiertos se aplican de uno en uno, con una ejecución después de cada uno, para atribuir
cada efecto a su causa.
