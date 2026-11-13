# AGORA

**Fecha:** 2026-11-12.
**Alcance:** qué es AGORA, cómo responde al reto *Research Agent Teams*, cómo se instala y ejecuta,
y qué evidencia hay de que funciona con un modelo real.

AGORA (Arquitectura de Gestión y Orquestación de Razonamiento Agéntico) es un sistema multiagente
escrito en Python, sin frameworks de agentes. Recibe una tarea de software, la investiga, la
especifica, la implementa y audita cada paso. Cuando el auditor rechaza un resultado, la fase se
repite con el veredicto como retroalimentación.

## 1. Flujo

```mermaid
flowchart LR
    T([Tarea]) --> P[Planning<br/>Investigador] --> R[PRD<br/>Producto] --> S[Spec<br/>Arquitecto] --> I[Implementation<br/>Desarrollador] --> E([Entrega])
    A{{Auditor}} -.-> P & R & S & I
```

Cada fase la ejecuta un agente experto que entrega un **artefacto**: un documento JSON validado con
Pydantic (`ResearchBrief`, `PRD`, `Spec`, `Implementation`). Los artefactos se enlazan por
identificadores: cada pedido del usuario (`ASK`) lo cubre un requisito (`REQ`), cada requisito una
prueba planeada (`T`), y cada prueba tiene un resultado medido con pytest.

## 2. Respuesta a cada punto del reto

| El reto pide | Dónde está | Archivo |
|---|---|---|
| Orquestador en streaming | Generador asíncrono que entrega un evento por cada paso mientras los agentes trabajan | `orchestrator.py` |
| Al menos tres agentes expertos | Cuatro: Investigador, Producto, Arquitecto y Desarrollador | `agent.py`, `developer.py`, `prompts.py` |
| Delegación | Cada tarea lista se entrega al agente de su nombre, con los artefactos de sus dependencias como entrada | `orchestrator.py` |
| Seguimiento de tareas | Tablero con máquina de estados (transiciones permitidas en una tabla), dependencias como grafo y guardado en SQLite | `board.py`, `store.py` |
| Reglas de validación y agente auditor | Esquema Pydantic por artefacto y reglas en código por fase: cobertura `ASK → REQ → T`, referencias colgantes, archivos Python, pruebas ejecutadas y aprobadas | `contracts.py`, `auditor.py` |
| Re-ejecución | Reintento del agente con el error de validación (hasta 3) y repetición de la fase con el veredicto del auditor (hasta 3) | `agent.py`, `orchestrator.py` |
| Registro, excepciones y rastreo por agente | Una línea JSON por evento, errores propios por tipo de fallo y versiones de cada artefacto en SQLite | `eventlog.py`, `errors.py`, `store.py` |
| Punto de entrada donde el usuario ve y pide cambios | Terminal con el árbol de tareas en vivo, tabla de trazabilidad al final y `--change` con confirmación y cascada | `cli.py`, `terminal.py` |

El principio que ordena todo: **el modelo propone y el código dispone**. Las decisiones que
gobiernan el proceso (qué se acepta, qué se repite, cuándo se detiene) están en código y tienen
pruebas, de modo que el comportamiento del sistema se puede probar sin gastar tokens.

## 3. Instalación

Requiere Python 3.12 o superior. En Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

## 4. Ejecución

```powershell
python -m agora [petición] [opciones]
```

| Opción | Qué hace | Por defecto |
|---|---|---|
| `petición` | La tarea a construir, entre comillas | La petición del inventario |
| `--real` | Usa el modelo de OpenRouter configurado en `.env` en lugar del simulado | Modelo simulado, sin tokens |
| `--run-id NOMBRE` | Nombre de la ejecución. Con él se nombran su carpeta de código y su registro, y se identifica al reanudarla o pedirle un cambio | `run-` con la fecha y la hora |
| `--resume` | Reanuda la ejecución `--run-id` sin repetir lo aprobado | — |
| `--change FASE TEXTO` | Pide un cambio a la ejecución terminada `--run-id`. Entra por `FASE` (`research`, `prd`, `spec` o `implementation`), muestra qué fases se rehacen y pide confirmación | — |
| `--pausa SEGUNDOS` | Con el simulado, espera antes de cada respuesta, como un modelo real | 0 |
| `-h`, `--help` | Muestra la ayuda | — |

Cada ejecución deja su código en `workspace/<run-id>/`, su registro de eventos en
`logs/<run-id>.jsonl` y el estado de su tablero en `workspace/agora.db`.

**Con el modelo simulado**, sin tokens:

```powershell
python -m agora
```

Ejecuta las cuatro fases sobre una tarea de ejemplo (un inventario de productos). El guion del
simulado hace que el primer PRD olvide un pedido del usuario: el auditor lo rechaza y el segundo
intento pasa. El código generado queda en `workspace/<ejecución>/` y el registro de eventos en
`logs/<ejecución>.jsonl`. Con `--pausa 2`, el simulado espera dos segundos antes de cada respuesta,
como un modelo real, y se ve en la terminal qué tarea está trabajando y cuánto lleva.

**Con un modelo real**, con `OPENROUTER_API_KEY` y `OPENROUTER_MODEL` en `.env`:

```powershell
python -m agora --real "Una API para consultar un inventario de productos y filtrarlos por categoria"
```

Peticiones de ejemplo, de menor a mayor dificultad:

| Nivel | Petición | Qué pone a prueba | Ejecutada con modelo real |
|---|---|---|---|
| Básico | `"Una API para consultar un inventario de productos y filtrarlos por categoria"` | Dos pedidos y una sola función de consulta | Sí, `real-1` a `real-19` (sección 5) |
| Intermedio | `"Un sistema de prestamos para una biblioteca: prestar y devolver libros, impedir prestar un libro que ya esta prestado y listar los prestamos vencidos"` | Estado que cambia (prestado o devuelto), una regla de negocio y fechas, que las pruebas deben fijar para ser repetibles | Sí, `real-20`: completa, cada fase al primer intento |
| Difícil | `"Un sistema de reservas de salas de juntas: reservar una sala en un horario, rechazar reservas que se traslapen, cancelar reservas y consultar que salas estan libres en un horario"` | Cuatro pedidos que enlazar en la trazabilidad y traslape de intervalos con casos límite, como dos reservas contiguas | Sí, `real-21`: completa, con un rechazo de la Spec; un pedido quedó cubierto a medias (sección 5) |

Las peticiones se escriben sin acentos para evitar problemas de codificación en la terminal de
Windows.

**Reanudar** una ejecución interrumpida, sin repetir lo aprobado:

```powershell
python -m agora --run-id <ejecución> --resume
```

**Pedir un cambio** a una ejecución terminada. Entra por la fase indicada, muestra qué se rehace y
pide confirmación:

```powershell
python -m agora --run-id <ejecución> --change prd "Agregar busqueda por nombre"
```

## 5. Evidencia con modelo real

Se hicieron veintiuna ejecuciones con dos modelos de OpenRouter. Sobre la petición básica, con
`qwen/qwen3-coder-30b-a3b-instruct` y la configuración final, tres de las últimas cuatro
completaron la cadena; antes de los dos últimos cambios, una de seis. Las peticiones intermedia y
difícil se completaron en su primera ejecución. Al leer su código aparecen defectos que las reglas
no detectan, como un pedido cubierto a medias: las reglas garantizan la cobertura, no la calidad.
Cada falla, su causa, el cambio que provocó y su efecto están en
[docs/hallazgos-modelo-real.md](docs/hallazgos-modelo-real.md).

## 6. Código

| Módulo | Responsabilidad |
|---|---|
| `contracts.py` | Artefactos de cada fase como modelos Pydantic |
| `llm.py`, `openrouter.py` | Conector de modelos, modelo simulado y cliente de OpenRouter con reintentos |
| `agent.py` | Agente base: llama al modelo, valida y reintenta con el error |
| `developer.py` | Desarrollador: escribe el código en la carpeta de trabajo y mide sus pruebas con pytest |
| `board.py`, `store.py` | Tablero de tareas, máquina de estados, dependencias y persistencia |
| `orchestrator.py` | Delegación, auditoría por fase, re-ejecución y eventos |
| `auditor.py` | Reglas en código y veredicto con evidencia |
| `search.py`, `workspace.py` | Búsqueda en Tavily, escritura acotada y pytest con límite de tiempo |
| `cli.py`, `terminal.py`, `eventlog.py` | Punto de entrada, árbol en vivo, entrega y registro |
| `demo.py`, `prompts.py` | Guion del modelo simulado e instrucciones de cada experto |

## 7. Verificación

```powershell
ruff check .
pytest
```

Las pruebas usan el modelo simulado y respuestas HTTP grabadas: no llaman a ningún servicio externo.

## 8. Documentos

- [docs/arquitectura.md](docs/arquitectura.md): arquitectura en breve, para revisión.
- [docs/arquitectura-detalle.md](docs/arquitectura-detalle.md): diseño completo, con notas de lo que
  cambió al implementarse.
- [docs/reglas.md](docs/reglas.md): qué recibe y entrega cada agente, y las reglas del auditor con
  su severidad y el motivo de cada una.
- [docs/hallazgos-modelo-real.md](docs/hallazgos-modelo-real.md): ejecuciones con modelo real,
  causas y decisiones.

## 9. Límites conocidos

- La interfaz es solo la terminal: el foco del reto fue el orquestador. El orquestador entrega los
  eventos como un flujo y la terminal es solo uno de sus consumidores, así que una interfaz web
  (React con Vite) sería otro consumidor: un servicio que transmita los eventos al navegador, sin
  cambiar el orquestador.
- El código generado contiene la lógica de lo pedido y sus pruebas, en Python sin paquetes
  externos, pero no levanta un servicio: para una API no hay servidor HTTP. Las pruebas corren en
  el mismo entorno que AGORA, donde no se instalan dependencias del código generado. Ejecutarlo
  como servicio requiere un entorno aislado por ejecución (un entorno virtual o un contenedor) con
  una lista de paquetes permitidos.
- Las reglas que requieren comparar significados (por ejemplo, que cada pedido aparezca en la tarea
  original) necesitan un juez con modelo, que no está implementado.
- La fase de Planning no usa todavía la búsqueda web; sus fuentes no se verifican.
- Una fase rechazada se repite a sí misma; no sube a la fase anterior cuando el defecto nace antes.
- Solo Implementation recibe en el reintento su respuesta anterior; las demás fases reciben solo
  el último veredicto.
- El costo de cada ejecución no se registra.
- El código generado se ejecuta sin aislamiento, solo acotado a su carpeta de trabajo.
