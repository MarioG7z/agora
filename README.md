# AGORA

Arquitectura de Gestión y Orquestación de Razonamiento Agéntico: un sistema multiagente que recibe
una tarea de software, la investiga, la especifica, la implementa y audita cada paso.

- Arquitectura: [docs/arquitectura.md](docs/arquitectura.md)
- Arquitectura en detalle: [docs/arquitectura-detalle.md](docs/arquitectura-detalle.md)

## Instalación

Requiere Python 3.12 o superior. En Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

## Ejecución con el modelo simulado

```powershell
python -m agora
```

Ejecuta las cuatro fases sobre una tarea de ejemplo (un inventario de productos) sin gastar
tokens. El primer PRD olvida un pedido del usuario, el auditor lo rechaza y el segundo intento
pasa. El código generado queda en `workspace/<ejecución>/` y el registro de eventos en
`logs/<ejecución>.jsonl`. Para reanudar una ejecución interrumpida:

```powershell
python -m agora --run-id <ejecución> --resume
```

## Ejecución con un modelo real

Con `OPENROUTER_API_KEY` y `OPENROUTER_MODEL` en `.env` (ver `.env.example`):

```powershell
python -m agora --real "Una API para consultar un inventario de productos"
```

Cada ejecución hace al menos cuatro llamadas al modelo, más una por cada rechazo del auditor o
reintento de formato.

## Verificación

```powershell
ruff check .
pytest
```
