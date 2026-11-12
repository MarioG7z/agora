# Hallazgos de las corridas con modelo real

**Fecha:** 2026-11-11.
**Alcance:** tres ejecuciones de AGORA con un modelo real sobre la tarea de ejemplo. Recoge qué
falló, la causa comprobada o la hipótesis, qué se cambió y qué queda por decidir.

## 1. Condiciones

| Dato | Valor |
|---|---|
| Modelo | `mistralai/ministral-8b-2512`, vía OpenRouter, el mismo para los cuatro expertos |
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

## 7. Decisiones

**Tomadas**

1. El error de esquema incluye el último error de validación.
2. El cliente de OpenRouter pide salida JSON con `response_format`.

**Abiertas**

1. Regla C en el auditor: los archivos de código de la Spec deben ser Python (`.py`). Protege en
   código lo que hoy depende del modelo.
2. Indicar en el prompt del Arquitecto que la solución sea en Python y la más pequeña que cubra los
   requisitos. Es una instrucción que faltaba, respaldada por el hallazgo 5.
3. Limitar en Planning el número de pedidos, o hacer que el auditor advierta cuando una petición
   corta produce muchos pedidos.
4. Registrar cada llamada al modelo como evento, con sus tokens y costo, para medir el costo de una
   ejecución (criterio de B8).
5. Probar un modelo más capaz para la fase de Implementation, que es la que escribe más texto.

Los cambios abiertos se aplican de uno en uno, con una ejecución después de cada uno, para atribuir
cada efecto a su causa.
