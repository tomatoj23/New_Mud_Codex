# New_Mud Engine

New_Mud is a Django/ASGI rewrite of the XKX100 MUD runtime. The current codebase
implements the M0 engineering skeleton and executable contract baseline defined
by `requirements_v6.md` (`requirements_v5.md` is retained as the historical
baseline). Public operation additionally requires the independent
`PublicV1Gate` / `RELEASE-001`.

## Local setup

Prerequisites:

- Python 3.14.2
- PostgreSQL 18.4
- Docker Compose is optional for the local database

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_private_python.ps1
docker compose up -d postgres
Copy-Item .env.example .env
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

The bootstrap script puts a private CPython runtime in `.venv\runtime` before
creating the virtual environment. This keeps `pyvenv.cfg` and all commands
inside the repository instead of depending on a user-profile Python install.
`requirements.lock` freezes the complete runtime, development, and packaging
toolchain resolved for this baseline.

Run all M0 gates with:

```powershell
.\.venv\Scripts\python scripts\verify_m0.py
```

The source fixture generator takes an operator-supplied XKX100 directory. It
never records the machine-local absolute path in a contract artifact.

```powershell
.\.venv\Scripts\python scripts\generate_source_contracts.py `
  --source-root $env:XKX100_SOURCE_ROOT
```

## Health endpoints

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- WebSocket `/ws/v1/health/`

The readiness endpoint requires a working PostgreSQL connection. The liveness
endpoint and WebSocket probe only prove that the ASGI process is responsive.

## Documentation

- [Product requirements V6](requirements_v6.md)
- [Historical requirements V5](requirements_v5.md)
- [Documentation governance](docs/19_documentation_governance.md)
- [Domain glossary](CONTEXT.md)
- [Engineering terminology index](UBIQUITOUS_LANGUAGE.md)
- [Architecture decisions](docs/adr/)
- [Current implementation status](docs/new_engine/18_IMPLEMENTATION_STATUS.md)
- [Evennia 6.0 modernity and fit assessment](docs/20_evennia_modernity_assessment.md)
