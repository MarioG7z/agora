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

## Verificación

```powershell
ruff check .
pytest
```
