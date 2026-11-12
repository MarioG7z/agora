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

## Verificación

```powershell
ruff check .
pytest
```
