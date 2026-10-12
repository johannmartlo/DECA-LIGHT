# DECA LIGHT — ESTADO DEL PROYECTO (PROJECT_STATE.md)

**Fecha de actualización:** 13 de octubre de 2026
**Fase actual:** Fase 6 — Implementación de Adaptadores de Persistencia SQLAlchemy (Subfase 6.1 completada)
**Último commit conocido (Git):** `a70fbf313d5a3209375a549501c418013bfc8d8f` (`feat: add SQLAlchemy ORM models, initial Alembic migration and persistence tests` en rama `master`)
**Workspace:** `C:\Users\juani\Documents\Codex\2026-10-03\referenced-chatgpt-conversation-this-is-an`  
**Repositorio Remoto Oficial:** `https://github.com/johannmartlo/DECA-LIGHT` (Estado: 100% vacío, verificado no destructivamente)  
**Copia de Seguridad Externa:** `C:\Users\juani\Documents\Codex\2026-10-03\backup_deca_light_phase3a` (Estado: Intacta y verificada)

---

## 1. RESUMEN EJECUTIVO Y ESTADO DE GIT

El proyecto DECA Light avanza en la Fase 6 de persistencia relacional con SQLAlchemy 2.0 y Alembic.
Se ha completado con éxito la **Subfase 6.1**:
- Unificación del contrato `CompanyRepositoryPort` incorporando el método abstracto `save(company: Company) -> Company`.
- Implementación del primer adaptador de base de datos relacional: `SqlAlchemyCompanyRepository`.
- Creación de 8 tests de integración específicos con SQLite y `PRAGMA foreign_keys=ON;`.
- Verificación completa de la suite: **208 tests superados**, 0 fallos, 1 advertencia externa.
- La API de FastAPI continúa operando exclusivamente sobre repositorios en memoria (`InMemoryCompanyRepository`).
- La base de datos persistente `instance/deca.sqlite3` permanece intacta sin tablas ni migraciones aplicadas.

### Estado Actual del Working Tree
- **Rama:** `master`
- **Archivos modificados no commiteados (`M`):**
  - `MASTER_CONTEXT.md` (incorporada sección 56 sobre estrategia de automatización, IA, agentes y gobernanza)
  - `PROJECT_STATE.md` (actualizado a Fase 6 con Subfase 6.1 completada)
  - `src/application/ports/company_repository.py` (método abstracto `save` incorporado)
  - `src/infrastructure/repositories/__init__.py` (exportación de `SqlAlchemyCompanyRepository`)
- **Archivos nuevos no rastreados (`??`):**
  - `src/infrastructure/repositories/sqlalchemy_company_repository.py` (adaptador relacional de empresas)
  - `tests/integration/test_company_repository_sqlalchemy.py` (suite de 8 pruebas de integración)
- **Estado Remoto:**
  - `git ls-remote https://github.com/johannmartlo/DECA-LIGHT.git` verificado no destructivamente: repositorio virgen sin commits.
  - El push a GitHub permanece estrictamente bloqueado a la espera de la orden explícita del usuario: `"AUTORIZO PUSH"`.

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
9. **Suite Completa de Pruebas Automatizadas:**
   - Ejecución de `pytest -q`: **208 tests pasados**, 0 fallos, 1 advertencia de deprecación externa. Verificado en tiempo real.

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
- **Resultado:** **208 pasados, 0 fallos, 1 advertencia** (tiempo de ejecución: ~7.1 s).
- **Desglose de la Suite:**
  - **191 tests de línea base:**
    - Dominio: entidades, value objects (`Matricula`, `NIF`, `DeCAToken`), validaciones legales FOM/2861/2012, estados de expedición.
    - Aplicación: casos de uso (`ImportDocument`, `AssignVehicle`, `GenerateDeCA`, `DeliverEmail`), deduplicación y orquestación.
    - Infraestructura: parsers de PDF (`HispatecPdfImporter`, `CmrPdfImporter`), renderizador vectorial ReportLab, generador QR con Segno, almacenamiento en disco local y stubs de correo.
    - Presentación: API REST FastAPI con endpoints operativos (`/expediciones`, `/decas`, `/documents`, `/d/{token}`).
  - **9 tests de integración ORM generales (`tests/integration/test_persistence_orm.py`) con `PRAGMA foreign_keys=ON;`:**
    1. `test_alembic_upgrade_downgrade_cycle`: Ciclo DDL head/base.
    2. `test_multi_session_persistence`: Persistencia entre sesiones independientes.
    3. `test_json_snapshot_integrity`: Integridad del snapshot JSON y hash SHA-256.
    4. `test_multi_company_albaran_reference_sharing`: Albaranes compartidos entre empresas.
    5. `test_internal_id_uniqueness_enforced`: Unicidad de `internal_id` en BD.
    6. `test_deca_version_unique_constraint`: Unicidad de número de versión por DeCA.
    7. `test_deca_delete_restricted_when_versions_exist`: Protección H-01 en DeCA (`RESTRICT`).
    8. `test_removing_version_from_relationship_does_not_delete_version`: Preservación sin orphan deletion.
    9. `test_email_delivery_blocks_deletion_of_expedition_and_deca`: Protección H-01 en entregas (`RESTRICT`).
  - **8 tests de integración de adaptador de empresas (`tests/integration/test_company_repository_sqlalchemy.py`) con `PRAGMA foreign_keys=ON;`:**
    1. `test_save_and_get_by_id`: Guardado y recuperación por identificador de empresa.
    2. `test_get_by_id_non_existent`: Manejo de empresa inexistente retornando `None`.
    3. `test_update_existing_company`: Actualización de empresa existente y persistencia de cambios.
    4. `test_list_all_and_list_active`: Listado global y filtrado exclusivo de activas.
    5. `test_mapping_optional_fields_and_none_tax_id`: Mapeo de campos opcionales y NIF nulo.
    6. `test_persistence_across_independent_sessions`: Persistencia real entre sesiones cerradas.
    7. `test_duplicate_primary_key_direct_orm_integrity_error`: Rechazo de clave primaria duplicada con `IntegrityError`.
    8. `test_transactional_rollback_clears_uncommitted_state`: Reversión limpia con `session.rollback()`.
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

---

## 7. ACCIONES TODAVÍA NO REALIZADAS

1. **Subfase 6.2 — Adaptador de Expediciones:** Diagnóstico e implementación de `SqlAlchemyExpeditionRepository`.
2. **Subfase 6.3 — Adaptadores de DeCA y Envíos:** Crear `SqlAlchemyDeCARepository` y `SqlAlchemyEmailDeliveryRepository`.
3. **Inyección de Sesión de Base de Datos en FastAPI:** Actualizar `dependencies.py` para conmutar de forma configurable hacia los adaptadores SQLAlchemy cuando se autorice.
4. **Aplicación de Migración en Base Persistente:** Ejecutar `alembic upgrade head` sobre `instance/deca.sqlite3` cuando se autorice expresamente.
5. **Desarrollo de la Interfaz Web:** Construir la interfaz de usuario siguiendo las directrices de `DESIGN_SYSTEM.md`.
6. **Integración con Correo Corporativo:** Evaluar proveedor real, destinatarios, revisión previa, trazabilidad, reintentos e idempotencia.
7. **Almacenamiento Persistente Definitivo, Enlaces y QR:** Configurar el backend custodial de almacenamiento y el endpoint de inspección.
8. **Sincronización Inicial con GitHub:** Configurar `origin` y ejecutar `git push -u origin master` tras recibir autorización explícita.
9. **Evaluación de IA y Agentes:** Estudio futuro de modelos especializados y n8n cuando aporten valor demostrado.

---

## 8. SIGUIENTE PASO RECOMENDADO

**Subfase 6.2: Diagnóstico e Implementación del Adaptador de Expediciones (`SqlAlchemyExpeditionRepository`):**
1. Inspeccionar `ExpeditionRepositoryPort` y los métodos requeridos (`save`, `get_by_id`, `find_by_reference`, `list_pending_vehicle`, `next_internal_id`, `find_by_internal_id`, `find_duplicate_cargo`).
2. Diseñar el mapeo bidireccional entre la entidad `Expedition` (y sus Value Objects: `Matricula`, `NIF`, `Weight`, `ExpeditionStatus`, `VehicleType`) y `ExpeditionORM`.
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
