# DECA LIGHT — ESTADO DEL PROYECTO (PROJECT_STATE.md)

**Fecha de actualización:** 12 de octubre de 2026  
**Fase actual:** Fase 5 — Auditoría Técnica de Persistencia, Organización de Continuidad y Gobernanza  
**Último commit conocido (Git):** `60d11af8e26115e9c9aa304cd5b814bf8dd6e456` (`chore: establish DECA Light baseline` en rama `master`)  
**Workspace:** `C:\Users\juani\Documents\Codex\2026-10-03\referenced-chatgpt-conversation-this-is-an`  
**Repositorio Remoto Oficial:** `https://github.com/johannmartlo/DECA-LIGHT` (Estado: 100% vacío, verificado no destructivamente)  
**Copia de Seguridad Externa:** `C:\Users\juani\Documents\Codex\2026-10-03\backup_deca_light_phase3a` (Estado: Intacta y verificada)

---

## 1. RESUMEN EJECUTIVO Y ESTADO DE GIT

El proyecto DECA Light se encuentra en fase de consolidación técnica y transición hacia persistencia relacional real con SQLAlchemy 2.0 y Alembic.
Se ha establecido un commit de línea base local (`60d11af`), preservando 100% del código operativo y los tests unitarios.

### Estado Actual del Working Tree
- **Rama:** `master`
- **Archivos modificados no commiteados (`M`):**
  - `MASTER_CONTEXT.md` (ampliado con protocolo de continuidad, gobernanza multi-agente, decisiones innegociables y arquitectura consolidada)
  - `alembic.ini` (configuración de URL SQLite local y logging)
  - `alembic/env.py` (vinculación de `target_metadata = Base.metadata` y carga dinámica de `DATABASE_URL`)
  - `src/infrastructure/database/__init__.py` (re-exportación de `Base` y modelos)
  - `src/infrastructure/storage/filesystem_storage.py`
  - `src/infrastructure/storage/local_pdf_storage.py`
- **Archivos no rastreados (`??`):**
  - `PROJECT_STATE.md` (este documento de continuidad y bitácora)
  - `src/infrastructure/database/models.py` (10 modelos relacionales SQLAlchemy)
  - `alembic/versions/617cdc1ada8d_initial_tables.py` (migración inicial autogenerada de tablas DDL)
  - `tests/integration/test_persistence_orm.py` (suite de 6 tests de integración de persistencia relacional)
- **Estado Remoto:**
  - `git ls-remote https://github.com/johannmartlo/DECA-LIGHT.git` verificado no destructivamente: repositorio virgen sin commits.
  - El push a GitHub permanece bloqueado a la espera de la orden explícita del usuario: `"AUTORIZO PUSH"`.

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
6. **Línea Base Git y Copia de Seguridad Externa (Fase 3A y 3B):**
   - Copia de seguridad íntegra en `C:\Users\juani\Documents\Codex\2026-10-03\backup_deca_light_phase3a`. Verificada con `Test-Path`.
   - Commit inicial local `60d11af` generado en rama `master` con regla `.gitignore` corregida para `/storage/` e `/instance/`.
7. **Suite Completa de Pruebas Automatizadas:**
   - Ejecución de `pytest -q`: **197 tests pasados**, 0 fallos, 1 advertencia de deprecación externa. Verificado en tiempo real.

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
- **Resultado:** **197 pasados, 0 fallos, 1 advertencia** (tiempo de ejecución: ~10.3 s).
- **Desglose de la Suite:**
  - **191 tests de línea base:**
    - Dominio: entidades, value objects (`Matricula`, `NIF`, `DeCAToken`), validaciones legales FOM/2861/2012, estados de expedición.
    - Aplicación: casos de uso (`ImportDocument`, `AssignVehicle`, `GenerateDeCA`, `DeliverEmail`), deduplicación y orquestación.
    - Infraestructura: parsers de PDF (`HispatecPdfImporter`, `CmrPdfImporter`), renderizador vectorial ReportLab, generador QR con Segno, almacenamiento en disco local y stubs de correo.
    - Presentación: API REST FastAPI con endpoints operativos (`/expediciones`, `/decas`, `/documents`, `/d/{token}`).
  - **6 tests de integración ORM (`tests/integration/test_persistence_orm.py`):**
    1. `test_alembic_upgrade_downgrade_cycle`: Verifica que las migraciones DDL suben a `head` y bajan a `base` sin inconsistencias de esquema.
    2. `test_multi_session_persistence`: Comprueba que una entidad guardada y commiteada en una sesión de SQLAlchemy se recupera idéntica desde otra sesión independiente.
    3. `test_json_snapshot_integrity`: Asegura que el snapshot estructurado del DeCA se serializa y recupera en campo JSON con hash SHA-256 inalterado.
    4. `test_multi_company_albaran_reference_sharing`: Confirma que empresas distintas pueden compartir el mismo identificador de albarán sin conflicto.
    5. `test_internal_id_uniqueness_enforced`: Verifica que la restricción única a nivel de base de datos rechaza duplicados de `internal_id` (`TD-YYYY-NNNNN`).
    6. `test_deca_version_unique_constraint`: Verifica que la restricción `uq_deca_version_number` impide crear dos versiones con el mismo número de secuencia para un mismo DeCA.
- **Advertencias:** 1 advertencia de biblioteca externa (`StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead` en `fastapi.testclient`). No afecta a la ejecución ni al código del proyecto.

---

## 4. CONTRADICCIONES DETECTADAS ENTRE DOCUMENTOS ANTERIORES

Durante las auditorías de las Fases 2, 4 y 5 se han identificado las siguientes divergencias entre la documentación teórica previa y la realidad del código:

| Ámbito | Documentación Anterior (`ARCHITECTURE.md` / `DATA_MODEL.md`) | Realidad Verificada en Código | Estado y Resolución |
| :--- | :--- | :--- | :--- |
| **Persistencia Activa** | Afirma que el sistema utiliza `SqlAlchemyRepository` contra PostgreSQL / SQLite. | Los casos de uso y la API FastAPI (`dependencies.py`) utilizan exclusivamente `InMemoryExpedicionRepository` e `InMemoryDeCARepository`. | **Contradicción real.** Los modelos ORM se crearon en Fase 4, pero los adaptadores aún no están conectados. La app actual sigue siendo en memoria. |
| **Cobertura de Tests Relacionales** | Se asumía que la suite de pruebas validaba la persistencia completa de la base de datos. | Los 191 tests del commit base testeaban únicamente repositorios en memoria o stubs. | **Resuelto en Fase 4:** Se escribieron los primeros 6 tests de integración ORM sobre SQLAlchemy. |
| **Integridad Legal vs. Borrado en Cascada** | FOM/2861/2012 y `DATA_MODEL.md` exigen inmutabilidad absoluta y custodia de 1 año para DeCAs emitidos y entregas. | En `models.py` inicial, las claves foráneas de `DeCAVersionORM` y `EmailDeliveryORM` se generaron con `ondelete="CASCADE"`. | **Riesgo crítico detectado:** Si se borra un DeCA, se destruirían sus versiones y auditoría. Debe corregirse a `RESTRICT`. |
| **Publicación en GitHub** | Se aludía a trabajar sobre el repositorio GitHub de Tomates de Autor. | El repositorio remoto en GitHub (`https://github.com/johannmartlo/DECA-LIGHT`) está completamente vacío; todo el código estaba en local sin commits. | **Clarificado:** Se creó el commit base local `60d11af` y el push queda pendiente de autorización explícita. |
| **Unicidad de Albaranes** | Algunos diagramas asumían `reference` (número de albarán) como clave única global. | En la operativa real de múltiples empresas, dos empresas pueden emitir el albarán número "1024". | **Alineado:** La clave única global es `internal_id` (`TD-YYYY-NNNNN`) y la unicidad del albarán es compuesta: `(company_id, reference)`. |

---

## 5. PROBLEMAS Y RIESGOS PENDIENTES

### Riesgos Altos (Críticos para Integridad o Cumplimiento)
- **[RIESGO-H01] Borrado en Cascada en Tablas de Custodia Legal:**
  - *Descripción:* En `src/infrastructure/database/models.py`, `deca_versions.deca_id` y `email_deliveries.deca_id` tienen `ondelete="CASCADE"`.
  - *Impacto:* Un borrado accidental o malintencionado de un registro en `decas` eliminaría el historial de versiones del documento y las trazas de auditoría de envío por correo, contraviniendo la Orden FOM/2861/2012.
  - *Mitigación:* Cambiar `ondelete="CASCADE"` a `RESTRICT` en `models.py`, actualizar la migración Alembic y aplicar tests de verificación.

### Riesgos Medios (Arquitectura y Transición)
- **[RIESGO-M01] Desconexión de Persistencia en la API:**
  - *Descripción:* `src/presentation/api/dependencies.py` inyecta instancias en memoria. Al reiniciar el proceso de FastAPI se pierden todas las expediciones y DeCAs creados por la interfaz web.
  - *Mitigación:* Desarrollar los adaptadores `SqlAlchemyExpedicionRepository` y `SqlAlchemyDeCARepository` que implementen los puertos del dominio y conectarlos mediante inyección de dependencias de FastAPI.
- **[RIESGO-M02] Cambios Pendientes de Commit en Workspace:**
  - *Descripción:* Hay archivos modificados (`alembic.ini`, `alembic/env.py`, `__init__.py`, `filesystem_storage.py`, `local_pdf_storage.py`, `MASTER_CONTEXT.md`) y archivos nuevos (`models.py`, migración inicial, tests ORM, `PROJECT_STATE.md`) sin registrar en Git.
  - *Mitigación:* Realizar un commit atómico de la Fase 4/5 en cuanto se valide el ajuste de integridad relacional.

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

---

## 7. ACCIONES TODAVÍA NO REALIZADAS

1. **Ajuste de Claves Foráneas (H-01):** Modificar `models.py` para establecer `ondelete="RESTRICT"` en `deca_versions` y `email_deliveries`, y sincronizar la migración `617cdc1ada8d_initial_tables.py`.
2. **Commit Local de la Fase 4 y 5:** Registrar en Git los modelos ORM, la migración Alembic, los tests de persistencia y la documentación actualizada.
3. **Sincronización Inicial con GitHub:** Configurar el remoto `origin` y ejecutar `git push -u origin master` tras recibir autorización explícita.
4. **Implementación de Adaptadores de Persistencia:** Crear `SqlAlchemyExpedicionRepository`, `SqlAlchemyDeCARepository`, `SqlAlchemyTransportistaRepository` y `SqlAlchemyConfiguracionRepository`.
5. **Inyección de Sesión de Base de Datos en FastAPI:** Actualizar `dependencies.py` para proporcionar sesiones transaccionales de SQLAlchemy a los casos de uso.
6. **Tests de Aceptación End-to-End con Persistencia Real:** Verificar todo el flujo (importar PDF -> asignar matrícula -> generar DeCA -> descargar por token) persistido en SQLite / PostgreSQL.

---

## 8. SIGUIENTE PASO RECOMENDADO

1. **Ajustar la restricción de integridad relacional en `src/infrastructure/database/models.py`:**
   - Cambiar `ondelete="CASCADE"` a `RESTRICT` en `DeCAVersionORM.deca_id` y `EmailDeliveryORM.deca_id`.
   - Regenerar o ajustar la migración inicial en `alembic/versions/617cdc1ada8d_initial_tables.py`.
   - Re-ejecutar `pytest` para confirmar que los 197 tests siguen pasando al 100%.
2. **Generar el commit local de la Fase 4 y 5:**
   - Crear un commit estructurado: `feat: add SQLAlchemy 2.0 ORM models, initial Alembic migration and continuity documentation`.
3. **Solicitar autorización al usuario para publicar en GitHub:**
   - Presentar el comando exacto y esperar la confirmación `"AUTORIZO PUSH"`.
4. **Proceder con la Fase 6 (Implementación de Repositorios SQLAlchemy):**
   - Implementar los adaptadores de persistencia que conecten el dominio con la base de datos sin romper ningún caso de uso existente.


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

### 9.5 Riesgos que Siguen Abiertos
- **[RIESGO-M01] Desconexión de Persistencia en la API:** Los endpoints de FastAPI siguen inyectando repositorios en memoria (`InMemory*`). Los datos creados en runtime no persisten tras el reinicio del servidor.
- **[RIESGO-M02] Cambios Pendientes de Commit en Workspace:** Existen modificaciones pendientes de registro en Git (modelos, migraciones, tests y documentación).
- **[RIESGO-B01] StarletteDeprecationWarning:** Advertencia externa en `fastapi.testclient` relativa a `httpx2`.

### 9.6 Siguiente Paso Técnico Recomendado
1. **Commit Local de la Línea Base Relacional (Fases 4 y 5):**
   - Registrar en Git todos los cambios con mensaje convencional: `feat: implement SQLAlchemy 2.0 models with RESTRICT foreign keys, initial Alembic migration and continuity documentation`.
2. **Sincronización con GitHub (origin master):**
   - Presentar el comando al usuario y esperar la instrucción explícita `"AUTORIZO PUSH"`.
3. **Inicio de la Fase 6 (Adaptadores de Repositorio SQLAlchemy):**
   - Implementar los adaptadores (`SqlAlchemyExpedicionRepository`, `SqlAlchemyDeCARepository`, etc.) conectando los puertos del dominio con la base de datos relacional.
