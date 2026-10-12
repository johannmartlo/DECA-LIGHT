# DECA Light

**Aplicación ligera de gestión y automatización de Documentos Electrónicos de Control Administrativo (DeCA) para Tomates de Autor S.L.**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonal-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/Status-Fase%201%20%7C%20Skeleton-orange.svg)]()

---

## 1. ¿Qué es DECA Light?

**DECA Light** es una herramienta operativa complementaria y ágil diseñada específicamente para **Tomates de Autor S.L.** Su propósito exclusivo es agilizar y automatizar la generación, validación legal, almacenamiento seguro, entrega por correo electrónico al transportista y custodia reglamentaria de los **Documentos Electrónicos de Control Administrativo (DeCA)** exigidos por el Ministerio de Transportes para el transporte de mercancías por carretera.

> **Principio Fundamental:** *"ERP primero, DECA Light después"*. La aplicación no pretende sustituir a Hispatec ni competir con sus funcionalidades transaccionales de almacén. Resuelve específicamente la ventana operativa en la que la carta de porte o albarán ya ha sido expedido pero la matrícula definitiva del vehículo de tracción y carga se asigna en el muelle de expedición.

---

## 2. Marco Normativo de Referencia

La arquitectura y los validadores de DECA Light se rigen estrictamente por:
- **Resolución de 5 de junio de 2026, de la Dirección General de Transporte por Carretera y Ferrocarril** ([BOE-A-2026-12784](https://www.boe.es/buscar/act.php?id=BOE-A-2026-12784)), que establece las características de los sistemas y documentos DeCA:
  - Generación nativa digital en formato PDF ($\le 5\text{ MB}$).
  - Código QR incrustado con URL única HTTPS (TLS 1.2+).
  - Descarga directa inmediata del documento sin pantallas intermedias ni autenticación para los inspectores en carretera.
  - Expiración determinista del acceso público a los 7 días naturales tras la finalización del servicio.
  - Custodia legal inmutable de los ficheros durante al menos 1 año.
- **Orden FOM/2861/2012** ([BOE-A-2013-154](https://www.boe.es/buscar/act.php?id=BOE-A-2013-154)), que determina los datos sustantivos y obligatorios de la carga, cargador, transportista efectivo y vehículo.

---

## 3. Estado Actual del Proyecto

Actualmente el proyecto se encuentra en:
$$\mathbf{FASE\ 1\ —\ SKELETON\ MODULAR\ Y\ DOCKER}$$

En esta fase se ha construido el andamiaje técnico base:
- Arquitectura Limpia (Hexagonal) desacoplada con 4 capas estrictas.
- Configuración centralizada y tipada mediante Pydantic Settings.
- Dominio aislado con modelos de entidades y Value Objects para vehículos (Rígido vs. Articulado).
- Interfaces/puertos abstractos para importación, persistencia, generación PDF, correo y auditoría.
- Adaptadores iniciales y stubs para desarrollo local y testing.
- Servidor web FastAPI con endpoint `GET /healthz` y manejo seguro de excepciones.
- Configuración agnóstica de Docker multi-stage y Docker Compose.
- Suite de pruebas automatizadas con pytest en verde y cobertura $> 90\%$.

---

## 4. Arquitectura del Sistema

El software sigue el patrón de Puertos y Adaptadores (Arquitectura Hexagonal):

```
deca-light/
├── src/
│   ├── domain/               # Entidades puras, Value Objects, Enums (sin frameworks)
│   ├── application/          # Casos de uso, DTOs y Puertos abstractos (Interfaces)
│   ├── infrastructure/       # Base de datos SQLAlchemy, Storage, Logging, PDF, Email
│   ├── presentation/         # API FastAPI, rutas y endpoint /healthz
│   ├── config/               # Configuración centralizada Pydantic Settings
│   └── main.py               # Punto de entrada de la aplicación
├── tests/
│   ├── unit/                 # Tests unitarios de dominio y configuración
│   ├── integration/          # Tests de integración (/healthz, storage, stubs)
│   └── conftest.py           # Fixtures de prueba aisladas
├── docs/                     # Especificaciones de arquitectura (ADRs, Threat Model, etc.)
├── Dockerfile                # Imagen OCI multi-stage con usuario no-root
├── docker-compose.yml        # Orquestación de desarrollo local
└── pyproject.toml            # Dependencias y herramientas fijadas
```

---

## 5. Requisitos de Ejecución

- **Python 3.12+**
- Gestor de paquetes `pip`
- Opcional: Docker y Docker Compose para ejecución contenerizada.

---

## 6. Instalación y Ejecución Local

### Paso 1: Clonar o situarse en el repositorio
```bash
cd deca-light
```

### Paso 2: Crear y activar entorno virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Paso 3: Instalar dependencias en modo editable
```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

### Paso 4: Configurar variables de entorno
```bash
cp .env.example .env
```

### Paso 5: Iniciar el servidor de desarrollo
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Abrir en el navegador:
- Healthcheck: `http://localhost:8000/healthz`
- Documentación OpenAPI interactiva: `http://localhost:8000/docs` (si `DEBUG=true`)

---

## 7. Ejecución con Docker

DECA Light está diseñado para ejecutarse de forma agnóstica sin acoplamiento a ningún proveedor cloud específico:

### Construir y levantar con Docker Compose
```bash
docker compose up --build
```

El servicio responderá en `http://localhost:8000/healthz` con persistencia en los volúmenes montados `./instance` y `./storage`.

---

## 8. Ejecución de Tests y Calidad de Código

### Ejecutar suite de pruebas con cobertura
```bash
pytest -v --cov=src
```

### Ejecutar linter de calidad (Ruff)
```bash
ruff check src tests
```

---

## 9. Variables de Entorno Principales

| Variable | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | String | `development` | Entorno: `development`, `staging`, `production`, `test` |
| `APP_NAME` | String | `DECA Light` | Nombre del sistema |
| `APP_VERSION` | String | `0.1.0` | Versión del software |
| `DEBUG` | Boolean | `false` | Activa trazas detalladas y `/docs` |
| `APP_HOST` | String | `0.0.0.0` | Interfaz de red de enlace |
| `APP_PORT` | Integer | `8000` | Puerto de escucha HTTP |
| `SECRET_KEY` | String | *dev-key* | Clave secreta para tokens y cookies de sesión |
| `PUBLIC_BASE_URL` | String | `http://localhost:8000` | URL canónica para los QR de inspección |
| `DATABASE_URL` | String | `sqlite:///./instance/deca.sqlite3` | Conexión SQLAlchemy (SQLite o PostgreSQL) |
| `STORAGE_PATH` | String | `./storage` | Directorio local de almacenamiento de PDFs |
| `LOG_LEVEL` | String | `INFO` | Nivel de logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `EMAIL_PROVIDER` | String | `stub` | Proveedor de correo (`stub`, `smtp`, `m365`, `gmail`) |

---

## 10. Documentación Complementaria

Consulte los documentos técnicos en la carpeta raíz:
- [`ARCHITECTURE.md`](file:///c:/Users/juani/Documents/Codex/2026-10-03/referenced-chatgpt-conversation-this-is-an/ARCHITECTURE.md): Arquitectura completa y desacoplamiento.
- [`DATA_MODEL.md`](file:///c:/Users/juani/Documents/Codex/2026-10-03/referenced-chatgpt-conversation-this-is-an/DATA_MODEL.md): Modelo entidad-relación y campos detallados.
- [`SECURITY.md`](file:///c:/Users/juani/Documents/Codex/2026-10-03/referenced-chatgpt-conversation-this-is-an/SECURITY.md): Threat Model STRIDE y protección contra IDOR.
- [`ROADMAP.md`](file:///c:/Users/juani/Documents/Codex/2026-10-03/referenced-chatgpt-conversation-this-is-an/ROADMAP.md): Plan de desarrollo por fases del MVP.
- [`TECH_DECISIONS.md`](file:///c:/Users/juani/Documents/Codex/2026-10-03/referenced-chatgpt-conversation-this-is-an/TECH_DECISIONS.md): Registro de Decisiones de Arquitectura (ADRs).
- [`RISKS.md`](file:///c:/Users/juani/Documents/Codex/2026-10-03/referenced-chatgpt-conversation-this-is-an/RISKS.md): Matriz de riesgos y control de incertidumbres.
