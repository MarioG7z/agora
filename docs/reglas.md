# Reglas de los agentes y del auditor

**Fecha:** 2026-11-12.
**Alcance:** qué recibe cada agente de AGORA, qué se le pide, qué entrega y con qué reglas se
revisa su entrega, tal como están implementadas. Cada regla indica por qué existe; las que nacieron
de una ejecución con modelo real remiten a [hallazgos-modelo-real.md](hallazgos-modelo-real.md).
La fuente de verdad es el código: `prompts.py`, `contracts.py` y `auditor.py`.

## 1. Cómo se revisa una entrega

Cada entrega pasa por dos controles, en este orden:

| Control | Qué revisa | Si falla |
|---|---|---|
| **Esquema** (Pydantic, en `agent.py`) | La **forma**: que el JSON tenga los campos y tipos del contrato | El agente reintenta, hasta 3 veces, con el error de validación en su entrada. Agotados, la tarea falla |
| **Auditor** (`auditor.py`) | El **contenido**: cobertura entre fases, archivos y resultados de pruebas | La fase se repite, hasta 3 veces, con el veredicto en su entrada. Agotados, la tarea falla y la ejecución se detiene |

Una **regla** es una pregunta de sí o no sobre la entrega. Su **evidencia** es la lista de lo que
falló, por ejemplo los ids de los pedidos sin requisito. La mayoría de las reglas son diferencias de
conjuntos: lo que debería estar menos lo que está.

Cada regla tiene una **severidad**:

- **Bloqueante:** si falla, la entrega se rechaza.
- **Advertencia:** si falla, la entrega puede aprobarse, pero el texto de la regla y su evidencia
  aparecen en el veredicto. Sirve para explicar la causa cuando otra regla bloquea.

Además, todos los agentes reciben en su prompt la **forma** de la respuesta esperada, generada a
partir del contrato, en lugar del esquema JSON técnico (hallazgo 8).

## 2. Investigador (Planning)

**Entrada:** la petición del usuario, como texto.

**Se le pide:** el problema en una frase, cada cosa que el usuario pidió como un pedido (`ASK-1`,
`ASK-2`…) y los hallazgos que respaldan el trabajo, cada uno con su fuente. El prompt **define** qué
es un pedido: algo que el usuario pidió de forma explícita, nunca una pregunta de investigación ni
una funcionalidad que no pidió (hallazgo 8).

**Entrega:** `ResearchBrief` (`problem`, `asks`, `findings`).

| Regla | Severidad | Por qué existe |
|---|---|---|
| There is at least one ASK | Bloqueante | Sin pedidos no hay nada que cubrir en las fases siguientes |
| ASK ids are unique | Bloqueante | Los ids enlazan toda la cadena; uno repetido la vuelve ambigua |

## 3. Producto (PRD)

**Entrada:** el `ResearchBrief` aprobado.

**Se le pide:** los requisitos (`REQ-1`, `REQ-2`…), cada uno con criterios de aceptación que una
prueba pueda comprobar y, en `covers`, los pedidos que atiende. Todo pedido debe quedar cubierto.

**Entrega:** `PRD` (`requirements`).

| Regla | Severidad | Por qué existe |
|---|---|---|
| Every ASK is covered by a REQ | Bloqueante | Un pedido sin requisito es algo que el usuario pidió y nadie construirá. Es el rechazo de la demo con el modelo simulado |
| Every REQ covers an existing ASK | Bloqueante | Detecta referencias colgantes: un requisito que dice cubrir un pedido que no existe |
| Every REQ has acceptance criteria | Bloqueante | Sin criterios no hay qué probar en la Spec |
| REQ ids are unique | Bloqueante | Igual que en los pedidos |

## 4. Arquitecto (Spec)

**Entrada:** el `PRD` aprobado.

**Se le pide:** las interfaces, los archivos (código en `app/` y pruebas en `tests/`) y las pruebas
planeadas (`T-1`, `T-2`…). Todo requisito debe quedar cubierto por una interfaz y por una prueba. El
prompt pide un proyecto mínimo en Python, solo con archivos `.py` y sin documentación,
configuración ni despliegue (hallazgo 9).

**Entrega:** `Spec` (`interfaces`, `files`, `tests`).

| Regla | Severidad | Por qué existe |
|---|---|---|
| Every REQ is covered by an interface | Bloqueante | Un requisito sin interfaz no tendrá código que lo implemente |
| Every REQ is covered by a test | Bloqueante | Un requisito sin prueba no se podrá verificar |
| Every covered id exists in the PRD | Bloqueante | Referencias colgantes hacia el PRD. En `real-4` detectó 27 nombres de servicios usados como si fueran requisitos |
| File paths stay inside the workspace | Bloqueante | El código generado solo puede escribirse en su carpeta de trabajo |
| File paths are unique | Bloqueante | Dos archivos con la misma ruta se sobrescribirían |
| Every file is Python | Bloqueante | En `real-3` la Spec planeó 46 archivos en TypeScript y la implementación falló tras tres intentos; la regla adelanta ese fallo a la Spec, donde cuesta menos (hallazgo 7) |
| Planned tests have a test file | Bloqueante | En `real-10` y `real-11` se planearon pruebas sin ningún archivo bajo `tests/`, y el fallo se detectó tarde, en la implementación (hallazgo 9) |

## 5. Desarrollador (Implementation)

**Entrada:** la `Spec` aprobada. En un reintento recibe además el veredicto y **el código que
escribió en el intento anterior**, para corregirlo en lugar de reescribirlo desde cero
(hallazgos 10 y 11).

**Se le pide:** cada archivo con su contenido completo, en Python sin paquetes externos, y cada
función de prueba nombrada con el id de su prueba planeada (`test_t1_...` para `T-1`).

**Entrega:** el modelo entrega `CodeDraft` (cada archivo con su contenido). El sistema escribe los
archivos en la carpeta de trabajo, ejecuta pytest y arma el `Implementation` con los resultados
**medidos**: el modelo no reporta si sus pruebas pasan.

| Regla | Severidad | Por qué existe |
|---|---|---|
| Every file in the Spec was written | Bloqueante | El código debe corresponder a lo planeado |
| Every test in the Spec was run | Bloqueante | Cada prueba planeada debe tener un resultado, enlazado por su nombre |
| Every test passes | Bloqueante | Es la verificación final de los criterios de aceptación |
| pytest reports no errors | Bloqueante | Lleva al veredicto las líneas de error de pytest. En `real-9` el código importaba Flask, que no está instalado, y sin esa causa el modelo repitió el error tres veces (hallazgo 9) |
| Every test is named after its Spec id (test_t1_..., test_t2_...) | **Advertencia** | Explica por qué una prueba "no se ejecutó" cuando sí corrió con otro nombre. Es advertencia porque en `real-13` hubo pruebas extra con nombres libres y la ejecución era correcta. Incluir la forma esperada en el texto hizo que el modelo corrigiera los nombres en `real-19` (hallazgos 10 y 11) |
| No forbidden modules | Bloqueante | El código generado no debe usar `subprocess`, `os.system` ni `shutil.rmtree`. Se comprueba buscando el texto en cada archivo, una comprobación deliberadamente simple |

## 6. Límites conocidos de las reglas

- Las reglas en código garantizan **cobertura**, no calidad: una prueba puede existir, cubrir su
  requisito y pasar sin comprobar nada útil.
- No hay reglas que comparen significados, como que cada pedido aparezca en la petición original.
  Requieren un juez con modelo (sección 8.4 del diseño), que no está implementado.
- La regla de fuentes recuperadas en Planning no está implementada, porque la búsqueda web todavía
  no está conectada a esa fase.
- Solo el Desarrollador recibe en el reintento su respuesta anterior.
