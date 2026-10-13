# DECA LIGHT — ESTADO DEL PROYECTO (PROJECT_STATE.md)

**Fecha de actualización:** 13 de octubre de 2026
**Fase actual:** Fase 6 — Implementación de Adaptadores de Persistencia SQLAlchemy (Subfase 6.3.1 completada: Cierre de brechas de aislamiento multiempresa y concurrencia)
**Último commit conocido (Git):** `873ef91372d184e8fce22f7e8bf431434fea6ac4` (`feat: add SQLAlchemy company repository adapter` en rama `master`, sincronizado con `origin/master`)
**Workspace:** `C:\Users\juani\Documents\Codex\2026-10-03\referenced-chatgpt-conversation-this-is-an`  
**Repositorio Remoto Oficial:** `https://github.com/johannmartlo/DECA-LIGHT` (Estado: Sincronizado en commit `873ef91372d184e8fce22f7e8bf431434fea6ac4`)
**Copia de Seguridad Externa:** `C:\Users\juani\Documents\Codex\2026-10-03\backup_deca_light_phase3a` (Estado: Intacta y verificada)

---

## 1. RESUMEN EJECUTIVO Y ESTADO DE GIT

El proyecto DECA Light avanza en la Fase 6 de persistencia relacional con SQLAlchemy 2.0 y Alembic.
Se han completado con éxito la **Subfase 6.1**, la **Subfase 6.2** y la **Subfase 6.3.1**:
- **Subfase 6.1:** Unificación del contrato `CompanyRepositoryPort` y creación de `SqlAlchemyCompanyRepository` (8 tests de integración).
- **Subfase 6.2:** Implementación completa de `SqlAlchemyExpeditionRepository` con sus 7 métodos de contrato (`save`, `get_by_id`, `find_by_reference`, `list_pending_vehicle`, `next_internal_id`, `find_by_internal_id`, `find_duplicate_cargo`).
- **Subfase 6.3.1:** Cierre integral de brechas de aislamiento multiempresa y concurrencia transaccional:
  - Definición del Value Object de dominio `CompanyContext` y excepción `UnauthorizedCompanyContextException`.
  - Blindaje multiempresa en todos los casos de uso (`AssignVehicle`, `EmitDeCA`, `SendDeCAEmail`, `ValidateExpedition`, `ImportDocumentsBatch`).
  - Blindaje estricto contra mutaciones y reasignaciones cruzadas de empresa en `save()` (`CompanyMismatchException`).
  - Implementación de `save_with_id_retry()` con política discriminante `is_internal_id_collision` (descarta categóricamente errores de clave foránea o nulidad para no generar bucles infinitos de reintento).
- **Suite de pruebas completa:** **251 tests superados**, 0 fallos, 1 advertencia externa.
- La API de FastAPI continúa operando exclusivamente sobre repositorios en memoria (`InMemory*Repository`).
- La base de datos persistente `instance/deca.sqlite3` permanece intacta sin tablas ni migraciones aplicadas.

### Estado Actual del Working Tree
- **Rama:** `master`
- **Archivos modificados pendientes de commit (`M`):**
  - `MASTER_CONTEXT.md` (incorporadas sección 56 sobre IA/automatización y sección 57 sobre estrategia SaaS B2B)
  - `PROJECT_STATE.md` (actualizado a Fase 6 con Subfases 6.1 y 6.2 completadas)
  - `src/infrastructure/repositories/__init__.py` (exportación de adaptadores SQLAlchemy)
- **Archivos nuevos no rastreados (`??`):**
  - `src/infrastructure/repositories/sqlalchemy_expedition_repository.py` (adaptador relacional de expediciones)
  - `tests/integration/test_expedition_repository_sqlalchemy.py` (suite de 12 pruebas de integración)
- **Estado Remoto:**
  - `origin/master` sincronizado en commit `873ef91372d184e8fce22f7e8bf431434fea6ac4`.
  - No se realizan commits ni push sin autorización explícita.

---

## 2. CAMBIOS IMPLEMENTADOS Y SU NIVEL DE VERIFICACIÓN

Para evitar asunciones infundadas y discrepancias entre sesiones, cada componente implementado se clasifica según su grado de verificación empírica en el entorno local:

### 2.1 [VERIFICADO DIRECTAMENTE EN ESTA SESIÓN]
1. **Saneamiento del Prototipo Flask (Fase 1):**
   - Eliminación permanente de archivos obsoletos en raíz: `app.py`, `requirements.txt`, `templates/`, `static/`, `MASTER_CONTEXT.MD.txt`.
   - Verificado mediante inspección del filesystem y ausencia en `git status`.
2. **Infraestructura Base de Base de Datos y Alembic (Fase 1 y Fase 4):**
   - `src/infrastructure/database/session.py` expone `Base = declarative_base()`, `engine` y `SessionLocal`.
   - Inicialización de Alembic, vinculación de `target_metadata = Base.metadata` en `alembic/env.py` y carga dinámica de `DATABASE_URL`.
   - Verificado mediante inspección y ejecución de migraciones.
3. **Modelos ORM de Negocio (Fase 4):**
   - Creación de 10 modelos en `src/infrastructure/database/models.py`:
     - `ConfiguracionCargadorORM` (`configuracion_cargador`)
     - `DocumentoImportadoORM` (`documentos_importados`)
     - `TransportistaORM` (`transportistas`)
     - `TransportistaAliasORM` (`transportista_aliases`)
     - `VehiculoORM` (`vehiculos`)
     - `ExpedicionORM` (`expediciones`)
     - `ExpedicionBultoORM` (`expedicion_bultos`)
     - `DeCAORM` (`decas`)
     - `DeCAVersionORM` (`deca_versions`)
     - `EmailDeliveryORM` (`email_deliveries`)
   - Verificado mediante inspección de código y tests de persistencia.
4. **Migración Inicial de Base de Datos (Fase 4):**
   - Archivo `alembic/versions/617cdc1ada8d_initial_tables.py` con todas las sentencias DDL `create_table`, índices y restricciones.
   - Ciclo completo de migración verificado: `alembic upgrade head` seguido de `alembic downgrade base` ejecutado limpiamente sobre base de datos temporal sin errores.
5. **Aislamiento Multiempresa y Referencias Cruzadas (Fase 4):**
   - `company_id` implementado en `expediciones`, `decas`, `configuracion_cargador` y `email_deliveries`.
   - Verificado mediante test automatizado que dos empresas diferentes pueden coexistir con el mismo número de albarán (`reference`) sin colisión gracias a la clave unívoca interna `internal_id` (`TD-YYYY-NNNNN`).
7. **Línea Base Git y Consolidación de Fase 5 (Fases 3A, 3B y 5):**
   - Copia de seguridad íntegra en `C:\Users\juani\Documents\Codex\2026-10-03\backup_deca_light_phase3a`. Verificada con `Test-Path`.
   - Commit inicial local `60d11af` (`master`) y commit consolidado `a70fbf3` (`feat: add SQLAlchemy ORM models, initial Alembic migration and persistence tests`).
   - Mitigación del riesgo H-01 aplicada con `ondelete="RESTRICT"` y directrices visuales documentadas en `DESIGN_SYSTEM.md`.
8. **Adaptador de Persistencia de Empresas (`SqlAlchemyCompanyRepository` — Subfase 6.1):**
   - Puerto `CompanyRepositoryPort` unificado con `@abstractmethod def save(company: Company) -> Company`.
   - Implementado `SqlAlchemyCompanyRepository` con inyección de sesión SQLAlchemy, mapeo bidireccional puro (`_to_orm`, `_to_domain`), soporte completo para Value Object `NIF` (`valor`), alias documentales en JSON y gestión transaccional desacoplada basada en `session.flush()`.
   - Creada suite de 8 tests de integración (`tests/integration/test_company_repository_sqlalchemy.py`) sobre SQLite temporal con `PRAGMA foreign_keys=ON;`.
10. **Adaptador de Persistencia de Expediciones (`SqlAlchemyExpeditionRepository` — Subfase 6.2):**
   - Implementado `SqlAlchemyExpeditionRepository` en `src/infrastructure/repositories/sqlalchemy_expedition_repository.py`.
   - Implementa los 7 métodos del contrato `ExpeditionRepositoryPort`: `save`, `get_by_id`, `find_by_reference`, `list_pending_vehicle`, `next_internal_id`, `find_by_internal_id` y `find_duplicate_cargo`.
   - Mapeo bidireccional estricto entre `Expedition` y `ExpeditionORM`, preservando todos los Value Objects (`NIF`, `Matricula`, `Weight`, `VehicleType`, `ExpeditionStatus`).
   - Gestión transaccional desacoplada mediante `session.flush()` en `save()`, delegando la frontera transaccional en el caso de uso y sin ocultar `IntegrityError`.
   - Generación atómica y segura de `internal_id` (`TD-YYYY-NNNNN`) respaldada por la restricción física `UNIQUE` en base de datos (`uq_expeditions_internal_id`) y soporte para `SELECT FOR UPDATE` en PostgreSQL.
   - Creada suite de 12 tests de integración dedicados en `tests/integration/test_expedition_repository_sqlalchemy.py` sobre SQLite temporal con `PRAGMA foreign_keys=ON;`.
11. **Suite Completa de Pruebas Automatizadas:**
   - Ejecución de `pytest -q`: **220 tests pasados**, 0 fallos, 1 advertencia de deprecación externa. Verificado en tiempo real.

### 2.2 [PENDIENTE DE VERIFICACIÓN / HISTÓRICO NO CONTRASTADO EN ESTA SESIÓN]
1. **Adaptador Transaccional de Microsoft Graph API v1.0:**
   - La arquitectura y documentación (`MICROSOFT_GRAPH_SETUP.md`, `ADR-015`) especifican el envío transaccional mediante OAuth 2.0 y Microsoft Graph API. Existen contratos y stubs, pero la comunicación real contra un tenant de Azure AD / Office 365 con credenciales corporativas reales está pendiente de verificación con credenciales activas.
2. **Empaquetado y Ejecución en Contenedor Docker:**
   - El archivo `Dockerfile` / `docker-compose.yml` está documentado (`ADR-002`), pero no se ha compilado ni arrancado la imagen en esta sesión.
3. **Ingesta de Lotes Reales de Albaranes de Producción:**
   - Los parsers de PDF (`pdfplumber` / `pypdf`) han pasado todos los tests unitarios con los fixtures del repositorio (`tests/fixtures/`), pero la extracción con muestras reales recientes y masivas de albaranes de Hispatec ERP está pendiente de validación en entorno de integración con usuarios finales.
4. **Comportamiento en Motor PostgreSQL de Producción:**
   - Los tests de persistencia y migraciones de Alembic se han verificado localmente sobre SQLite en memoria y SQLite WAL. El comportamiento específico de tipos (ej. `JSON` / `JSONB`, transacciones concurrentes) sobre un cluster de PostgreSQL 16+ está pendiente de verificación en entorno staging.

---

## 3. PRUEBAS EJECUTADAS Y RESULTADOS

- **Herramienta:** `pytest` 8.x sobre entorno virtual Python 3.12.10 (`.venv`).
- **Comando:** `.venv\Scripts\pytest -q`
- **Resultado:** **251 pasados, 0 fallos, 1 advertencia** (tiempo de ejecución: ~8.5 s).
- **Desglose de la Suite:**
  - **191 tests de línea base:**
    - Dominio: entidades, value objects (`Matricula`, `NIF`, `DeCAToken`), validaciones legales FOM/2861/2012, estados de expedición.
    - Aplicación: casos de uso (`ImportDocument`, `AssignVehicle`, `GenerateDeCA`, `DeliverEmail`), deduplicación y orquestación.
    - Infraestructura: parsers de PDF (`HispatecPdfImporter`, `CmrPdfImporter`), renderizador vectorial ReportLab, generador QR con Segno, almacenamiento en disco local y stubs de correo.
    - Presentación: API REST FastAPI con endpoints operativos (`/expediciones`, `/decas`, `/documents`, `/d/{token}`).
  - **13 tests unitarios de `CompanyContext` (`tests/unit/test_company_context.py`):**
    - Validación canónica de formato (`^[A-Z0-9_]{2,40}$`), saneamiento de espacios en blanco, rechazo de nulos/vacíos y validación de `is_verified` (`UnauthorizedCompanyContextException`).
  - **4 tests unitarios de aislamiento multiempresa en Casos de Uso (`tests/unit/test_use_case_multi_tenant.py`):**
    - `AssignVehicleToExpeditionUseCase`: rechazo de acceso cruzado entre empresas y rechazo de contexto no verificado.
    - `ValidateExpeditionUseCase`: validación protegida por tenant.
    - `EmitDeCAUseCase`: rechazo de emisión para expediciones de otra empresa.
    - `SendDeCAEmailUseCase`: rechazo de envío transaccional cruzado.
  - **5 tests unitarios de repositorio en memoria (`tests/unit/test_in_memory_expedition_repository.py`):**
    - Aislamiento estricto por tenant en `get_by_id`, `find_by_reference`, `save` y `find_by_internal_id`.
    - Detección de mutaciones en memoria mediante copia profunda y rechazo de reasignación cruzada de empresa (`CompanyMismatchException`).
  - **9 tests de integración ORM generales (`tests/integration/test_persistence_orm.py`) con `PRAGMA foreign_keys=ON;`:**
    - Ciclo Alembic, sesiones independientes, integridad JSON, albaranes compartidos, clave única de identificador interno, protecciones `RESTRICT`.
  - **8 tests de integración de adaptador de empresas (`tests/integration/test_company_repository_sqlalchemy.py`) con `PRAGMA foreign_keys=ON;`:**
    - Operaciones CRUD completas sobre `CompanyORM`, mapeo de Value Objects `NIF`, transacciones independientes y reversión.
  - **21 tests de integración de adaptador de expediciones (`tests/integration/test_expedition_repository_sqlalchemy.py`) con `PRAGMA foreign_keys=ON;`:**
    - Guardado y recuperación completa de todos los campos y Value Objects.
    - Aislamiento multiempresa en `get_by_id`, `find_by_reference`, `list_pending_vehicle`, `find_by_internal_id`.
    - Rechazo de mutaciones y reasignaciones cruzadas en `save()` (`CompanyMismatchException`).
    - Detección de colisiones en concurrencia real sobre dos sesiones independientes (`IntegrityError`).
    - Validación de `save_with_id_retry()` ante colisión de `internal_id`: recuperación automática con reintento.
    - Rechazo inmediato sin reintentos espurios ante errores de clave foránea (`ForeignKeyViolation`).
    - Propagación de excepción al superar el límite de reintentos (`max_retries`).
- **Advertencias:** 1 advertencia de biblioteca externa (`StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead` en `fastapi.testclient`). No afecta a la ejecución ni al código del proyecto.

---

## 4. CONTRADICCIONES DETECTADAS ENTRE DOCUMENTOS ANTERIORES

Durante las auditorías de las Fases 2, 4 y 5 se han identificado las siguientes divergencias entre la documentación teórica previa y la realidad del código:

| Ámbito | Documentación Anterior (`ARCHITECTURE.md` / `DATA_MODEL.md`) | Realidad Verificada en Código | Estado y Resolución |
| :--- | :--- | :--- | :--- |
| **Persistencia Activa** | Afirma que el sistema utiliza `SqlAlchemyRepository` contra PostgreSQL / SQLite. | Los casos de uso y la API FastAPI (`dependencies.py`) utilizan exclusivamente `InMemoryExpedicionRepository` e `InMemoryDeCARepository`. | **Contradicción real.** Los modelos ORM se crearon en Fase 4, pero los adaptadores aún no están conectados. La app actual sigue siendo en memoria. |
| **Cobertura de Tests Relacionales** | Se asumía que la suite de pruebas validaba la persistencia completa de la base de datos. | Los 191 tests del commit base testeaban únicamente repositorios en memoria o stubs. | **Resuelto en Fase 4 y 5:** Se escribieron 9 tests de integración ORM sobre SQLAlchemy con claves foráneas activas. |
| **Integridad Legal vs. Borrado en Cascada** | FOM/2861/2012 y `DATA_MODEL.md` exigen inmutabilidad absoluta y custodia de 1 año para DeCAs emitidos y entregas. | En `models.py` inicial, las claves foráneas de `DeCAVersionORM` y `EmailDeliveryORM` se generaron con `ondelete="CASCADE"`. | **Resuelto y consolidado en commit `a70fbf3`:** Corregido a `RESTRICT` en modelos, migración y verificado con 3 tests dedicados. |
| **Publicación en GitHub** | Se aludía a trabajar sobre el repositorio GitHub de Tomates de Autor. | El repositorio remoto en GitHub (`https://github.com/johannmartlo/DECA-LIGHT`) está completamente vacío; todo el código estaba en local sin commits. | **Clarificado:** Se creó el commit base local `60d11af` y el push queda pendiente de autorización explícita. |
| **Unicidad de Albaranes** | Algunos diagramas asumían `reference` (número de albarán) como clave única global. | En la operativa real de múltiples empresas, dos empresas pueden emitir el albarán número "1024". | **Alineado:** La clave única global es `internal_id` (`TD-YYYY-NNNNN`) y la unicidad del albarán es compuesta: `(company_id, reference)`. |

---

## 5. PROBLEMAS Y RIESGOS PENDIENTES

### Riesgos Mitigados en Fase 5
- **[RIESGO-H01] Borrado en Cascada en Tablas de Custodia Legal:**
  - *Estado:* Resuelto y consolidado en el commit local `a70fbf3`. Restricciones `ForeignKey(..., ondelete="RESTRICT")` implementadas en `deca_versions` y `email_deliveries`, retirada de `cascade="all, delete-orphan"` en `DeCAORM.versions` y verificado mediante 3 tests de integración con claves foráneas activas.

### Riesgos Medios (Arquitectura y Transición)
- **[RIESGO-M01] Desconexión de Persistencia en la API:**
  - *Descripción:* `src/presentation/api/dependencies.py` inyecta instancias en memoria (`InMemory*Repository`). Los modelos SQLAlchemy existen, pero los adaptadores todavía no están conectados a los casos de uso. Al reiniciar el proceso de FastAPI se pierden las expediciones y DeCAs en memoria.
  - *Mitigación:* Desarrollar los adaptadores de repositorio SQLAlchemy y conectarlos mediante inyección de dependencias de FastAPI.
- **[RIESGO-M02] Base de Datos Local de Trabajo (`instance/deca.sqlite3`):**
  - *Descripción:* La base de datos persistente no contiene todavía las tablas de negocio y no se ha migrado.
  - *Mitigación:* No debe considerarse migrada ni ejecutarse `alembic upgrade head` sobre ella hasta recibir autorización expresa.
- **[RIESGO-M03] Interfaz Web (Frontend) Pendiente:**
  - *Descripción:* La aplicación aún no dispone de interfaz de usuario web interactiva.
  - *Mitigación:* Se implementará en su fase correspondiente siguiendo las directrices de `DESIGN_SYSTEM.md`.
- **[RIESGO-M04] Correo Corporativo y Almacenamiento en la Nube:**
  - *Descripción:* El envío transaccional desde cuenta corporativa real y el almacenamiento en la nube definitivo siguen pendientes de sus fases respectivas.
  - *Mitigación:* Evaluar el proveedor real de correo y diseñar la infraestructura en las fases autorizadas.

### Riesgos Bajos (Mantenibilidad)
- **[RIESGO-B01] StarletteDeprecationWarning:**
  - *Descripción:* Advertencia producida por `fastapi.testclient` al importar `httpx`.
  - *Mitigación:* Actualizar dependencias de testing cuando se gestione el archivo definitivo de dependencias (`pyproject.toml` / `requirements.txt`).

---

## 6. DECISIONES CONFIRMADAS

1. **Monolito Modular con Arquitectura Limpia:** Separación estricta entre Dominio, Aplicación, Infraestructura y Presentación. Dominio 100% puro y agnóstico.
2. **Inmutabilidad Documental:** El snapshot canónico de un DeCA se sella con hash SHA-256 y sus versiones no admiten sobrescritura ni borrado físico.
3. **Inspección Pública Anti-IDOR:** Los códigos QR y las URLs de verificación (`/d/{token}`) utilizan un token criptográfico efímero de 256 bits (`secrets.token_urlsafe(32)`), desvinculado de las claves primarias internas.
4. **Extracción Determinista:** Ingesta de albaranes de Hispatec mediante parsing geométrico nativo (`pdfplumber` / `pypdf`) y regex, sin modelos de lenguaje en el pipeline crítico.
5. **Aislamiento Multiempresa:** Separación lógica por `company_id` con soporte para albaranes repetidos entre distintas razones sociales.
6. **Coexistencia de Repositorios:** No se eliminarán los repositorios en memoria hasta que los repositorios SQLAlchemy estén completamente operativos y validados con tests.
7. **Control Estricto de Remoto Git:** Ningún comando de publicación (`git push`) se ejecutará sin la orden explícita del usuario (`"AUTORIZO PUSH"`).
8. **Estrategia de Automatización, IA y Gobernanza (Sección 56 de `MASTER_CONTEXT.md`):**
   - Automatización determinista como núcleo innegociable de la lógica de negocio y transacciones.
   - IA especializada reservada exclusivamente para estudio futuro ante casos atípicos o no estructurados.
   - Agentes de IA limitados con permisos mínimos, sin capacidad para saltarse validaciones ni emitir documentos incompletos.
   - n8n como posibilidad de orquestación externa sin sustituir a FastAPI ni a PostgreSQL.
   - Gobernanza estricta: diagnóstico previo, no inventar clases/estados, pruebas continuas y autorización expresa para migraciones, commits y pushes.
9. **Estrategia de Producto: Mentalidad de Producto Comercializable como SaaS B2B (Decisión del 13 de octubre de 2026; Sección 57 de `MASTER_CONTEXT.md`):**
   - **Decisión comercial:** Tomada el 13 de octubre de 2026 para desarrollar DECA Light con mentalidad de producto comercializable como SaaS B2B.
   - **Objetivo:** Desarrollar un único producto de software comercializable, reutilizable tanto por la empresa inicial como por futuros clientes.
   - **Unicidad de código:** No se mantendrán versiones paralelas ni se duplicará la lógica de negocio para comercializarlo; las diferencias entre clientes se resolverán mediante configuración y adaptadores cuando corresponda.
   - **Núcleo agnóstico y desacoplamiento:** El núcleo de dominio permanece independiente de clientes concretos; las integraciones con ERP se mantendrán desacopladas del núcleo.
   - **Aislamiento y pilares técnicos:** La arquitectura deberá permitir aislamiento estricto de datos por empresa, usuarios y permisos. Se priorizan la persistencia fiable, la integridad transaccional, la seguridad, la auditoría, la trazabilidad y las pruebas.
   - **Equilibrio arquitectónico:** Se debe evitar tanto el acoplamiento a una empresa concreta como la complejidad SaaS prematura; las nuevas funcionalidades comerciales se incorporarán mediante fases explícitas.
   - **Validación y salvaguardas legales:** La demanda de mercado y la disposición a pagar deberán validarse antes de invertir en una plataforma comercial completa; la titularidad del código y las obligaciones de confidencialidad deberán revisarse antes de comercializar el producto.
   - **Estado técnico vigente y límites:**
     - Estado técnico: Subfase 6.1 (empresas) y Subfase 6.2 (expediciones) completadas y verificadas empíricamente; Subfase 6.3 (DeCA y envíos) pendiente.
     - Último commit publicado conocido en GitHub: `873ef91372d184e8fce22f7e8bf431434fea6ac4`.
     - La API sigue utilizando repositorios en memoria.
     - **Aclaración expresa de límites:** Esta decisión estratégica NO significa que el producto ya sea multiempresa, que esté preparado para producción ni que exista demanda comercial validada. No se ha implementado todavía la arquitectura SaaS multiempresa completa.

---

## 7. ACCIONES TODAVÍA NO REALIZADAS

1. **Subfase 6.3 — Adaptadores de DeCA y Envíos:** Crear `SqlAlchemyDeCARepository` y `SqlAlchemyEmailDeliveryRepository`.
2. **Inyección de Sesión de Base de Datos en FastAPI:** Actualizar `dependencies.py` para conmutar de forma configurable hacia los adaptadores SQLAlchemy cuando se autorice.
3. **Aplicación de Migración en Base Persistente:** Ejecutar `alembic upgrade head` sobre `instance/deca.sqlite3` cuando se autorice expresamente.
4. **Desarrollo de la Interfaz Web:** Construir la interfaz de usuario siguiendo las directrices de `DESIGN_SYSTEM.md`.
5. **Integración con Correo Corporativo:** Evaluar proveedor real, destinatarios, revisión previa, trazabilidad, reintentos e idempotencia.
6. **Almacenamiento Persistente Definitivo, Enlaces y QR:** Configurar el backend custodial de almacenamiento y el endpoint de inspección.
7. **Sincronización con GitHub:** Preparar commit local y ejecutar `git push -u origin master` cuando se autorice expresamente.
8. **Evaluación de IA y Agentes:** Estudio futuro de modelos especializados y n8n cuando aporten valor demostrado.

---

## 8. SIGUIENTE PASO RECOMENDADO

**Subfase 6.3: Diagnóstico e Implementación de Adaptadores de DeCA y Envíos (`SqlAlchemyDeCARepository` y `SqlAlchemyEmailDeliveryRepository`):**
1. Inspeccionar `DeCARepositoryPort` y `EmailDeliveryRepositoryPort` junto con sus modelos ORM (`DeCAORM`, `DeCAVersionORM`, `EmailDeliveryORM`).
2. Diseñar el mapeo bidireccional preservando snapshots JSON, hash SHA-256 y relaciones con DeCAVersion.
3. Crear suite de pruebas de integración con SQLite temporal y `PRAGMA foreign_keys=ON;`.
4. Mantener la API y casos de uso en memoria sin alteraciones.


---

## 9. RESOLUCIÓN DEL RIESGO H-01 Y VALIDACIÓN DE RESTRICCIONES (FASE 5 - EJECUCIÓN)

**Fecha de ejecución:** 12 de octubre de 2026 (23:15 CEST)  
**Estado:** Resuelto y verificado empíricamente con 200 tests pasando al 100%.

### 9.1 Resultado Exacto de la Corrección del Riesgo H-01
Se ha mitigado el riesgo de destrucción en cascada del historial documental legal aplicando protecciones físicas en la base de datos relacional:
1. **`DeCAVersionORM` (`deca_versions.deca_id`):** Modificada la restricción de clave foránea a `ForeignKey("decas.id", ondelete="RESTRICT")`. Impide físicamente borrar un `DeCA` si existen versiones históricas asociadas.
2. **`EmailDeliveryORM` (`email_deliveries.deca_id` y `expedition_id`):** Modificadas las claves foráneas a `ForeignKey("decas.id", ondelete="RESTRICT")` y `ForeignKey("expeditions.id", ondelete="RESTRICT")`. Impide físicamente borrar una expedición o un `DeCA` si existen registros de auditoría de entrega por correo.
3. **`DeCAORM.versions`:** Se ha eliminado la configuración `cascade="all, delete-orphan"` de la relación ORM. Al retirar una versión de la colección en memoria (`deca.versions.remove(v)`), SQLAlchemy ya no emite una sentencia `DELETE` sobre la base de datos, garantizando que las versiones físicas se preserven intactas.
*Nota legal:* Estas medidas constituyen salvaguardas técnicas y físicas de base de datos a nivel de esquema; el cumplimiento normativo integral de la Orden FOM/2861/2012 requiere además la aplicación coordinada de las políticas del dominio y la inmutabilidad de los ficheros PDF almacenados.

### 9.2 Listado de Archivos Modificados
- `src/infrastructure/database/models.py`: Retirada de `cascade="all, delete-orphan"` en `DeCAORM.versions`; actualización de `ondelete="RESTRICT"` en `DeCAVersionORM` y `EmailDeliveryORM`.
- `alembic/versions/617cdc1ada8d_initial_tables.py`: Corrección directa de las sentencias DDL iniciales para reflejar `ondelete="RESTRICT"` en las claves foráneas de `deca_versions` y `email_deliveries`.
- `tests/integration/test_persistence_orm.py`: Inyección obligatoria de `PRAGMA foreign_keys=ON;` en el motor de pruebas SQLite y creación de 3 nuevos tests de integración referencial (`test_deca_delete_restricted_when_versions_exist`, `test_removing_version_from_relationship_does_not_delete_version`, `test_email_delivery_blocks_deletion_of_expedition_and_deca`).

### 9.3 Estado Final de las Migraciones Alembic
- **Estrategia aplicada:** Se editó directamente la migración inicial `617cdc1ada8d_initial_tables.py` tras comprobar empíricamente que:
  1. La base de datos persistente local `instance/deca.sqlite3` tenía la tabla `alembic_version` vacía (sin ninguna migración aplicada) y ninguna tabla de negocio creada.
  2. La migración era exclusivamente local (archivo no trackeado en Git, sin commits previos y no publicada en remoto).
- **Validación aislada:** Se ejecutó con éxito `alembic upgrade head` seguido de `alembic downgrade base` sobre una base de datos temporal aislada (`temp_migration_test.sqlite3`), confirmando la correcta creación y eliminación de todas las tablas con restricciones `RESTRICT`.

### 9.4 Pruebas Ejecutadas y Resultados Literales
- **Comando de integración ORM:** `.venv\Scripts\pytest tests/integration/test_persistence_orm.py -v`
  - *Resultado:* **9 passed, 1 warning in 2.64s**
- **Comando de suite completa:** `.venv\Scripts\pytest`
  - *Resultado:* **200 passed, 1 warning in 11.51s**
- **Cobertura de las nuevas pruebas:**
  - *Test 1 (`test_deca_delete_restricted_when_versions_exist`):* Demuestra que el intento de borrado físico de un DeCA con versiones lanza un `IntegrityError` por `ON DELETE RESTRICT`.
  - *Test 2 (`test_removing_version_from_relationship_does_not_delete_version`):* Demuestra que remover una versión de la lista en memoria `deca.versions.remove(v)` no emite `DELETE` y mantiene la fila física intacta en la base de datos tras la transacción.
  - *Test 3 (`test_email_delivery_blocks_deletion_of_expedition_and_deca`):* Demuestra que los registros de `EmailDeliveryORM` impiden el borrado de expediciones y DeCAs asociados.

### 9.5 Estado Posterior al Commit de Fase 5
- **[RIESGO-H01] Resuelto:** Verificado con 9 tests ORM (3 nuevos dedicados a borrado restringido) y consolidado en el commit `a70fbf3`.
- **[RIESGO-M01] Desconexión de Persistencia en la API:** Los endpoints de FastAPI siguen inyectando repositorios en memoria (`InMemory*Repository`). Los adaptadores SQLAlchemy aún no están conectados a los casos de uso.
- **[RIESGO-M02] Base de Datos Local de Trabajo (`instance/deca.sqlite3`):** No contiene tablas de negocio y no se ha migrado; no debe considerarse migrada sin autorización expresa.
- **[RIESGO-B01] StarletteDeprecationWarning:** Advertencia externa en `fastapi.testclient` relativa a `httpx2`.

---

## 10. CONSOLIDACIÓN DE LA FASE 5 Y REFERENCIA ESTRATÉGICA

**Fecha de consolidación:** 12 de octubre de 2026 (23:36 CEST)
**Commit consolidado:** `a70fbf313d5a3209375a549501c418013bfc8d8f`
**Mensaje:** `feat: add SQLAlchemy ORM models, initial Alembic migration and persistence tests`

### 10.1 Estado de Consolidación
- Auditoría técnica de persistencia comunicada con dictamen **APTO PARA COMMIT LOCAL**.
- Suite de pruebas completa: **200 pasadas, 0 fallos, 1 advertencia**.
- 10 modelos ORM creados en `src/infrastructure/database/models.py`.
- Migración inicial `617cdc1ada8d_initial_tables.py` validada en base de datos temporal aislada con restricciones `RESTRICT`.
- La base persistente local `instance/deca.sqlite3` no contiene las tablas de negocio y no debe considerarse migrada hasta recibir autorización expresa.
- Los endpoints de FastAPI continúan utilizando repositorios en memoria.
- `DESIGN_SYSTEM.md` creado en la raíz del proyecto para documentar las directrices visuales del frontend inspiradas en CCO y SaaS modernos (Linear, Stripe, Shippo).
- Remoto GitHub oficial (`https://github.com/johannmartlo/DECA-LIGHT.git`) verificado no destructivamente: 100% virgen sin commits. Push bloqueado a la espera de `"AUTORIZO PUSH"`.

### 10.2 Referencia Estratégica a la Automatización, IA y Agentes
- Incorporada la Sección 56 a `MASTER_CONTEXT.md` (*Estrategia de automatización, inteligencia artificial y agentes*).
- Establece la automatización determinista y fiable como núcleo prioritario de la aplicación (extracción, albaranes, duplicados, emparejamiento de matrículas por albarán, validaciones legales y custodia).
- Reserva la inteligencia artificial para estudio futuro ante excepciones reales observadas (documentos atípicos, asistencia diagnóstica).
- Fija directrices para agentes de IA con permisos mínimos y control humano.
- n8n se contempla como posible orquestador externo futuro, sin sustituir a FastAPI ni a PostgreSQL.
- El envío por correo corporativo sigue pendiente de estudio de proveedor real, revisión previa, trazabilidad e idempotencia.
- *Nota de control:* Ninguna de estas capacidades futuras se considera implementada ni autorizada en esta fase.

---

## 11. IMPLEMENTACIÓN DE LA SUBFASE 6.1: ADAPTADOR DE EMPRESAS (SQLAlchemy)

**Fecha de ejecución:** 13 de octubre de 2026
**Estado:** Resuelto y verificado empíricamente con 208 tests pasando al 100%.

### 11.1 Alcance y Decisiones de Implementación
1. **Unificación de Contrato:**
   - Incorporado `@abstractmethod def save(self, company: Company) -> Company` en `CompanyRepositoryPort` (`src/application/ports/company_repository.py`), eliminando la asimetría histórica con `InMemoryCompanyRepository`.
2. **Adaptador `SqlAlchemyCompanyRepository`:**
   - Implementado en `src/infrastructure/repositories/sqlalchemy_company_repository.py`.
   - Inyección de sesión SQLAlchemy (`Session`).
   - Mapeo bidireccional puro:
     - `_to_orm`: extrae `company.tax_id.valor` (preservando el Value Object `NIF`), serializa `document_aliases` a lista JSON y persiste atributos escalares.
     - `_to_domain`: reconstituye `Company` con `NIF(orm.tax_id)` y `tuple(orm.document_aliases or [])`.
   - Gestión transaccional desacoplada: operaciones de escritura utilizan `session.flush()` sin emitir `commit()` forzado, permitiendo que la frontera transaccional superior o el caso de uso controle el commit/rollback de la unidad de trabajo.
3. **Pruebas de Integración (`test_company_repository_sqlalchemy.py`):**
   - 8 tests automatizados ejecutados sobre base de datos SQLite temporal con `PRAGMA foreign_keys=ON;`:
     - Guardado e inserción.
     - Actualización de empresa existente.
     - Recuperación por identificador (existente e inexistente).
     - Listado completo y filtrado exclusivo de empresas activas.
     - Mapeo de Value Objects (`NIF`) y campos opcionales.
     - Persistencia real entre sesiones independientes cerradas.
     - Restricción de clave primaria duplicada (`IntegrityError`).
     - Reversión transaccional limpia con `session.rollback()`.
4. **Garantía de Aislamiento:**
   - FastAPI (`dependencies.py`) sigue proveyendo `InMemoryCompanyRepository`.
   - La base de datos persistente `instance/deca.sqlite3` no fue tocada ni migrada.
   - No se realizó ningún commit ni push a Git.

---

## 12. IMPLEMENTACIÓN DE LA SUBFASE 6.2: ADAPTADOR DE EXPEDICIONES (SQLAlchemy)

**Fecha de ejecución:** 13 de octubre de 2026
**Estado:** Resuelto y verificado empíricamente con 220 tests pasando al 100%.

### 12.1 Alcance y Decisiones de Implementación
1. **Adaptador `SqlAlchemyExpeditionRepository`:**
   - Implementado en `src/infrastructure/repositories/sqlalchemy_expedition_repository.py`.
   - Implementa íntegramente `ExpeditionRepositoryPort` con los métodos: `save`, `get_by_id`, `find_by_reference`, `list_pending_vehicle`, `next_internal_id`, `find_by_internal_id` y `find_duplicate_cargo`.
   - Inyección de sesión SQLAlchemy (`Session`).
   - Mapeo bidireccional puro `_to_orm` y `_to_domain`:
     - Preservación de Value Objects: `NIF` (`valor`), `Matricula` (`valor`), `Weight` (`kg`), `VehicleType` (StrEnum), `ExpeditionStatus` (StrEnum).
     - Mapeo de `company_id`: vacío `""` en dominio se traduce a `None` en ORM para respetar la restricción `ForeignKey("companies.company_id", ondelete="RESTRICT")`, y `None` relacional se restituye a `""` en dominio.
     - Conservación exacta del número de albarán/referencia (`reference`).
     - Metadatos de extracción serializados como `dict` hacia `JSON`.
2. **Estrategia de Concurrencia para `internal_id` (`TD-YYYY-NNNNN`):**
   - Sin bloqueos en memoria de tipo `threading.Lock()` (ineficaces en multiproceso).
   - Consulta el máximo identificador del ejercicio fiscal (`ORDER BY internal_id DESC LIMIT 20`) analizando el sufijo numérico para calcular el siguiente correlativo secuencial.
   - En PostgreSQL aplica `with_for_update()` para bloqueo de fila.
   - La seguridad física ante concurrencia está garantizada por la restricción `UNIQUE` (`uq_expeditions_internal_id`) en base de datos. Ante colisión concurrente, la base de datos rechaza la inserción elevando `IntegrityError` en `session.flush()`, permitiendo que el caso de uso invocador reintente de forma segura sin ocultar errores.
3. **Estrategia Transaccional:**
   - Operaciones de escritura ejecutan exclusivamente `session.flush()`.
   - Prohibido terminantemente ejecutar `commit()` o `rollback()` dentro del repositorio; la frontera transaccional permanece en el caso de uso (Capa de Aplicación).
4. **Pruebas de Integración (`test_expedition_repository_sqlalchemy.py`):**
   - 12 tests automatizados ejecutados sobre SQLite temporal con `PRAGMA foreign_keys=ON;` y semillero de empresas padre:
     1. Guardado y recuperación completa de todos los campos y Value Objects.
     2. Recuperación por UUID inexistente retorna `None`.
     3. Actualización de datos operativos (estado, vehículo, transportista).
     4. Búsqueda por referencia con aislamiento estricto por empresa (multiempresa).
     5. Búsqueda por identificador visible `TD-YYYY-NNNNN`.
     6. Listado de pendientes de matrícula con y sin filtro de empresa.
     7. Generación consecutiva segura por ejercicio fiscal.
     8. Detección de duplicados de carga con tolerancia de peso (±0.01 kg).
     9. Rechazo por empresa inexistente con `IntegrityError` (`PRAGMA foreign_keys=ON;`).
     10. Rechazo por duplicidad de `internal_id` con `IntegrityError`.
     11. Reversión transaccional limpia controlada por el invocador con `session.rollback()`.
     12. Mapeo correcto de campos opcionales y nulos.
5. **Garantía de Aislamiento:**
   - FastAPI (`dependencies.py`) sigue proveyendo repositorios en memoria (`InMemory*Repository`).
   - La base de datos persistente `instance/deca.sqlite3` no fue tocada ni migrada.
   - No se realizó ningún commit ni push a Git.

---

## 13. IMPLEMENTACIÓN DE LA SUBFASE 6.3.1: BLINDAJE MULTIEMPRESA Y POLÍTICA DE CONCURRENCIA

**Fecha de ejecución:** 13 de octubre de 2026  
**Estado:** Resuelto y verificado empíricamente con **251 tests pasando al 100%**.

### 13.1 Brechas Identificadas y Solución Técnica Aplicada
Tras la auditoría independiente de persistencia, se detectaron brechas residuales en el control de acceso multi-tenant y en la gestión de reintentos por colisión de identificadores. Se han implementado las siguientes correcciones:

1. **Contrato de Contexto Empresarial Autorizado (`CompanyContext`):**
   - Implementado como Value Object inmutable en `src/domain/value_objects.py`.
   - Excepción formal `UnauthorizedCompanyContextException` en `src/domain/exceptions.py`.
   - Valida el formato canónico mediante expresión regular `^[A-Z0-9_]{2,40}$`, rechaza identificadores nulos o vacíos, normaliza espacios en blanco y exige verificación de autoridad (`is_verified=True`).
   - Impide que identificadores arbitrarios o cabeceras HTTP sin verificar penetren en la capa de dominio.

2. **Blindaje de los Casos de Uso (Anti-IDOR Multi-Tenant):**
   - `AssignVehicleToExpeditionUseCase`: valida `CompanyContext`, exige y pasa `company_id` a `expedition_repo.get_by_id(..., company_id=...)` y a `expedition_repo.save(..., company_id=...)`.
   - `EmitDeCAUseCase`: valida `CompanyContext`, recupera la expedición acotada al tenant y persiste la transición de estado preservando el tenant.
   - `SendDeCAEmailUseCase`: valida `CompanyContext`, restringe la expedición y el envío transaccional al tenant autorizado.
   - `ValidateExpeditionUseCase`: soporta parámetro `company_id`, impidiendo la inspección de expediciones pertenecientes a otras empresas.
   - `ImportDocumentsBatchUseCase`: persiste expediciones mediante `save_with_id_retry(..., company_id=detected_company_id)`.

3. **Invariantes contra Mutaciones y Reasignaciones Cruzadas en `save()`:**
   - Tanto `SqlAlchemyExpeditionRepository` como `InMemoryExpeditionRepository` imponen validaciones estrictas:
     - Si una expedición persistida tiene empresa asignada, está terminantemente prohibido alterar o eliminar su asociación empresarial (`CompanyMismatchException`).
     - Si el contexto `company_id` del invocador no coincide con la empresa de la entidad, la operación se rechaza inmediatamente.
   - En `InMemoryExpeditionRepository` se implementó copia defensiva (`copy.copy`) en el almacenamiento interno para evitar que mutaciones de aliasing por referencia en memoria eludan la comparación de estado previo.

4. **Política Bounded y Selectiva de Reintentos (`save_with_id_retry`):**
   - Declarado en `ExpeditionRepositoryPort` e implementado con control transaccional en `SqlAlchemyExpeditionRepository`.
   - Servicio de política `is_internal_id_collision(exc)` en `src/domain/services/internal_id_collision_policy.py`:
     - Discrimina específicamente la restricción `uq_expeditions_internal_id` (incluyendo análisis de `pgcode == '23505'` y metadatos diagnósticos en PostgreSQL).
     - Descarta y propaga inmediatamente violaciones de claves foráneas (`FOREIGN KEY`, ej. empresa inexistente), restricciones de nulidad (`NOT NULL`) o restricciones `CHECK`. Esto previene de forma absoluta bucles infinitos de reintento sobre datos corruptos.
     - Ante colisión real de `internal_id`: ejecuta `session.rollback()`, recalcula atómicamente `next_internal_id()` y reintenta la persistencia hasta un umbral acotado (`max_retries=3`).

### 13.2 Desglose de Pruebas y Verificación
- **13 pruebas unitarias de `CompanyContext`** (`tests/unit/test_company_context.py`).
- **4 pruebas unitarias de aislamiento en casos de uso** (`tests/unit/test_use_case_multi_tenant.py`).
- **5 pruebas unitarias de repositorio en memoria** (`tests/unit/test_in_memory_expedition_repository.py`).
- **21 pruebas de integración de SQLAlchemy** (`tests/integration/test_expedition_repository_sqlalchemy.py`), incorporando:
  - `test_save_with_id_retry_success_after_collision`: simulación de dos workers concurrentes donde el reintento automático resuelve la colisión y genera el siguiente correlativo secuencial.
  - `test_save_with_id_retry_rejects_foreign_key_violation_without_retry`: validación de que los errores de FK no se reintentan y se elevan de inmediato.
  - `test_save_with_id_retry_exceeds_max_retries`: propagación limpia de `IntegrityError` al agotar los intentos permitidos.
- **Suite completa:** **251 pruebas superadas al 100%**, 0 fallos.

### 13.3 Garantías de Aislamiento del Entorno
- La capa de presentación (`src/presentation/api/dependencies.py`) continúa proveyendo repositorios en memoria (`InMemory*Repository`). SQLAlchemy no se ha conectado a FastAPI.
- La base de datos persistente `instance/deca.sqlite3` permanece intacta (12.288 bytes, sin tablas de negocio aplicadas).
- No se han realizado commits ni operaciones de push en Git.

---

## 14. IMPLEMENTACIÓN DE LA SUBFASE 6.3.4: AUTENTICACIÓN M2M, AISLAMIENTO MULTIEMPRESA Y NUMERACIÓN INDEPENDIENTE

**Fecha de ejecución:** 13 de octubre de 2026  
**Estado:** Resuelto y verificado empíricamente con **268 pruebas superadas al 100%** (y 2 skips condicionales de PostgreSQL).

### 14.1 Alcance y Decisiones Implementadas

1. **Decisión A — Autenticación M2M (API Keys Seguras):**
   - **Contratos y Adaptadores:**
     - `TenantAuthenticatorPort` (`src/application/ports/tenant_authenticator_port.py`) define los métodos de autenticación de credenciales y resolución de la empresa activa.
     - `InMemoryTenantAuthenticator` (`src/infrastructure/auth/api_key_authenticator.py`) implementa la gestión de identidades y API keys.
     - Almacenamiento seguro mediante hashes criptográficos SHA-256 (`hash_api_key`) y validación en tiempo constante (`secrets.compare_digest`) para prevenir ataques de temporización (*timing attacks*).
   - **Esquema de Autorización en FastAPI:**
     - Dependencia `get_authorized_company_context` (`src/presentation/api/dependencies.py`) que inspecciona el esquema `Bearer` vía `HTTPBearer(auto_error=False)`.
     - Petición sin credencial o con API key inválida -> `401 Unauthorized` con cabecera `WWW-Authenticate: Bearer`.
     - Credencial con permisos sobre múltiples empresas sin cabecera `X-Company-Id` para desambiguar -> `400 Bad Request`.
     - Credencial intentando operar sobre una empresa no autorizada en su identidad -> `403 Forbidden`.
     - Credencial válida con empresa resuelta -> Retorna instancia de Value Object `CompanyContext(company_id=..., is_verified=True)`.
   - **Blindaje Anti-IDOR en Endpoints Protegidos:**
     - Rutas protegidas (`expedition_routes.py`, `deca_routes.py`, `import_routes.py`) inyectan `company_context` y acotan todas las consultas y mutaciones al `company_context.company_id`.
     - Respuestas uniformes `404 Not Found` ante recursos inexistentes o pertenecientes a otros tenants, impidiendo la deducción o fuga de información sobre la existencia de expediciones de terceros.
   - **Inspección Pública de Carretera:**
     - La ruta de acceso público `/d/{token}` se mantiene 100% abierta y no autenticada para permitir la visualización oficial en ruta del documento DeCA mediante tokens de alta entropía.

2. **Decisión B — Numeración Independiente por Empresa:**
   - **Secuenciación Particionada:**
     - El identificador visible de expedición (`TD-YYYY-NNNNN`) es independiente por empresa (`company_id`) y ejercicio fiscal (`fiscal_year`). Dos empresas distintas pueden tener simultáneamente la expedición `00001` de 2026.
     - Soporte para prefijo configurable por empresa (por defecto `"TD"`).
     - `InMemoryExpeditionSequenceGenerator` y `SqlAlchemyExpeditionRepository.next_internal_id` actualizados para calcular el correlativo filtrando por empresa y prefijo.
   - **Restricción Física Compuesta en Base de Datos:**
     - `ExpeditionORM` actualizado con restricción única compuesta `UNIQUE(company_id, internal_id)` nombrada `uq_expeditions_company_internal_id`.
     - Política de colisiones `is_internal_id_collision` adaptada para detectar tanto `uq_expeditions_company_internal_id` como los mensajes diagnósticos relacionales correspondientes.
     - Creada la migración Alembic `c3f89e41b212_unique_company_internal_id.py` para reflejar el cambio de restricción en PostgreSQL/SQLite.

3. **Decisión C — Persistencia y Aislamiento del Entorno:**
   - **Desconexión Intacta:** La API de FastAPI (`dependencies.py`) continúa operando en memoria; los adaptadores SQLAlchemy no se conectaron a la API.
   - **Base de Datos Local Protegida:** El archivo `instance/deca.sqlite3` no fue modificado, migrado ni alterado en modo alguno (12.288 bytes intactos).
   - **Suite de Concurrencia PostgreSQL:** Creada en `tests/integration/test_postgres_concurrency.py` con marcador `@pytest.mark.postgres` y omisión condicional controlada (`pytest.skip`) en ausencia de la variable de entorno `TEST_POSTGRES_URL`.
   - **Gobernanza Git:** No se realizó ningún commit ni push.

### 14.2 Desglose de Pruebas y Verificación

- **Suite completa:** **268 pruebas pasadas, 2 omitidas (PostgreSQL), 0 fallos, 1 advertencia en 13.52s**.
- **Nuevas pruebas unitarias e integración añadidas en la subfase:**
  - `tests/unit/test_api_key_auth.py`: 11 pruebas (autenticación M2M, comparación timing-safe, errores 401/403/400 y anti-IDOR).
  - `tests/unit/test_tenant_numbering.py`: 4 pruebas (generador en memoria por tenant, prefijos, unicidad compuesta en memoria y con base de datos SQLite real).
  - `tests/integration/test_postgres_concurrency.py`: 2 pruebas con skip condicional si no se define `TEST_POSTGRES_URL`.
- **Adaptación y validación de suites existentes:**
  - `test_expedition_api.py`, `test_deca_api.py`, `test_email_api.py`, `test_batch_import.py`, `test_public_endpoint.py`, `test_persistence_orm.py`, `test_company_and_multi_tenant.py`, `test_deca_engine_and_pdf.py`.

---

## 15. IMPLEMENTACIÓN DE LA SUBFASE 6.3.5: CORRECCIÓN DE AISLAMIENTO EN IMPORTACIÓN Y ROBUSTEZ TRANSACCIONAL

**Fecha de ejecución:** 13 de octubre de 2026  
**Estado:** Resuelto y verificado empíricamente con **273 pruebas superadas al 100%** (y 2 skips condicionales de PostgreSQL).

### 15.1 Alcance y Correcciones Implementadas

1. **Aislamiento Multiempresa en la Importación Documental Masiva:**
   - **Paso de Contexto en API:** `import_routes.py` inyecta `company_context` autenticado y pasa explícitamente `company_id=company_context.company_id` a `use_case.execute()`.
   - **Rechazo Estricto de Conflictos de Tenant:** En `ImportDocumentsBatchUseCase._process_single_file()`, si `CompanyDetector` detecta una empresa registrada en la plataforma diferente a la empresa autorizada (`detected_company_id != authorized_company_id`), el documento es **RECHAZADO INMEDIATAMENTE** con `status="REJECTED"`. Se descarta el hash de procesamiento, no se guarda el archivo físico en almacenamiento, no se crea entidad `Expedition` ni se inserta en base de datos.
   - **Preservación de Actores Operativos:** Los participantes reales del transporte (cargador, transportista, consignatario) extraídos del texto del documento se preservan íntegramente en los campos de dominio (`shipper_name`, `carrier_name_raw`, metadatos), mientras que la titularidad tenant queda gobernada por `authorized_company_id`.
   - **Tratamiento de Cargadores No Reconocidos:** Si el documento no coincide con ninguna empresa registrada en el sistema (`detected_company_id is None`), la expedición se atribuye al tenant autenticado (`company_id = authorized_company_id`), pero se clasifica como `status="NEEDS_REVIEW"` (`PENDIENTE_REVISION`) con `fields_needing_review.append("empresa_emisora")`. Se evitan registros huérfanos o con `company_id` nulo/falso.
   - **DTO Actualizado:** `BatchImportResultDTO` incorpora `rejected_count: int = 0` para consolidar el conteo de documentos rechazados por conflicto de tenant.

2. **Robustez Transaccional con Savepoints en `SqlAlchemyExpeditionRepository.save_with_id_retry`:**
   - Se eliminó la invocación a `self._session.rollback()`, que destruía la transacción externa del invocador y purgaba entidades agregadas/modificadas previamente en la misma sesión.
   - Se implementó aislamiento mediante savepoint relacional utilizando `with self._session.begin_nested(): return self.save(...)`.
   - Ante colisiones de `internal_id`, el context manager revierte exclusivamente el savepoint anidado, preservando intacta la sesión y cualquier objeto flusheado previamente en la unidad de trabajo. El reintento calcula el siguiente correlativo y vuelve a intentar dentro de un nuevo savepoint.

3. **Resolución Arquitectónica para la Nulabilidad de `company_id` en `ExpeditionORM`:**
   - En una arquitectura SaaS B2B, toda expedición pertenece obligatoriamente a una empresa cliente (`company_id`). Los documentos sin procesar corresponden a la entidad técnica `Document` (archivos fuente), no a expediciones de transporte.
   - La nulabilidad de la columna en `ExpeditionORM` se mantiene temporalmente a nivel relacional exclusivamente para retrocompatibilidad con esquemas históricos existentes, pero las fronteras de Dominio y Casos de Uso garantizan que en tiempo de ejecución ninguna expedición se guarde sin `company_id`.
   - Una vez autorizada la fase de migraciones persistentes sobre PostgreSQL, la columna se promoverá formalmente a `NOT NULL` con la restricción `UNIQUE (company_id, internal_id)`.

4. **Garantías de Aislamiento del Entorno:**
   - La API de FastAPI (`dependencies.py`) continúa utilizando los adaptadores en memoria (`InMemory*Repository`); SQLAlchemy no se conectó a FastAPI.
   - La base de datos persistente `instance/deca.sqlite3` permanece intacta (12.288 bytes, sin modificaciones).
   - No se ejecutaron migraciones, commits ni operaciones push en Git.

### 15.2 Desglose de Pruebas y Verificación

- **Suite completa:** **273 pruebas pasadas, 2 omitidas (PostgreSQL), 0 fallos, 1 advertencia en 11.36s**.
- **Nuevas pruebas añadidas en la subfase (5 pruebas):**
  - `test_batch_import_cross_tenant_pdf_rejected` (`tests/integration/test_batch_import.py`): verifica el rechazo inmediato de PDF perteneciente a otro tenant, con 0 persistencia y 0 escritura en almacenamiento.
  - `test_batch_import_unrecognized_shipper_assigned_to_authorized_tenant_needing_review` (`tests/integration/test_batch_import.py`): verifica la asignación al tenant autenticado con estado `NEEDS_REVIEW` ante cargador no registrado.
  - `test_batch_import_mix_valid_cross_tenant_and_unrecognized` (`tests/integration/test_batch_import.py`): verifica el comportamiento coordinado de un lote mixto de 3 documentos.
  - `test_api_import_batch_cross_tenant_rejection` (`tests/integration/test_batch_import.py`): verifica el rechazo de tenant cruzado a través del endpoint HTTP de FastAPI.
  - `test_save_with_id_retry_preserves_outer_transaction_state` (`tests/integration/test_expedition_repository_sqlalchemy.py`): verifica que el uso de savepoints preserva entidades flusheadas en la transacción externa ante reintentos por colisión.


