# DECA LIGHT — MATRIZ DE RIESGOS E INCERTIDUMBRES (CONSOLIDADA)
**Proyecto:** DECA Light  
**Empresa:** Tomates de Autor S.L.  
**Versión:** 1.5  
**Fecha:** 03/10/2026  
**Estado:** Gestión Preventiva de Riesgos Consolidada (Prompt 01.5)

---

## 1. CLASIFICACIÓN DE INCERTIDUMBRES Y ESTATUS ACTUAL

Se mantiene la trazabilidad de dudas e intervenciones humanas:
- `[REQUIERE CONFIRMACIÓN]`: Datos de negocio o muestras operativas pendientes de entrega por Tomates de Autor S.L.
- `[LEGAL_REVIEW_REQUIRED]`: Ratificación por asesoría legal o responsables de transporte.
- `[TECH_DECISION_REQUIRED]`: Configuración final del entorno de producción.

---

## 2. MATRIZ DE RIESGOS CONSOLIDADA

| ID | Categoría | Descripción del Riesgo | Prob. | Imp. | Estado / Tag | Mitigación Arquitectónica Consolidada |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | Arquitectura | Dependencia o bloqueo con un proveedor cloud concreto (*vendor lock-in*). | Baja | Alta | **RESUELTO (ADR-002)** | Empaquetado agnóstico en contenedor OCI (Docker); compatible con Cloud Run, VPS o local. |
| **RSK-02** | Legal / Operativa | Incumplimiento de datos de tracción y carga en camiones con semirremolque frigorífico. | Media | Alta | **RESUELTO (ADR-008)** | Tipificación obligatoria `RIGIDO` vs. `ARTICULADO` con validación estricta de ambas matrículas en articulados. |
| **RSK-03** | Legal / URL | Inexactitud o arbitrariedad en la expiración de la URL pública si se usan estimaciones por país. | Media | Media | **RESUELTO (ADR-009)** | Eliminadas todas las estimaciones. Expiración determinista calculada a 7 días de `fecha_fin_servicio`. |
| **RSK-04** | Seguridad | Raspado masivo o acceso no autorizado a los DeCAs mediante el endpoint público del QR. | Media | Crítica| **RESUELTO (ADR-004)** | Tokens opacos CSPRNG de 256 bits, Rate Limiting (30 req/min) y cabeceras `X-Robots-Tag`. |
| **RSK-05** | Operativa | Formato imprevisto o variable en los PDFs de carta de porte emitidos por Hispatec o CMR. | Media | Alta | **RESUELTO (Prompt 03.5)** | Parsers desacoplados (`CartaDePorteParser`, `CMRParser`, `CompositeDocumentParser`) con fallback a `PENDIENTE_REVISION` y trazabilidad `ExtractedField`. |
| **RSK-06** | Operativa | Ausencia de correo electrónico o matrícula para transportistas en muelle. | Alta | Media | **RESUELTO (Prompt 04)** | Caso de uso `AssignVehicleToExpeditionUseCase` permite captura simultánea de vehículo y actualización de transportista (nombre, NIF, email) en muelle. |
| **RSK-07** | Operativa | Datos fiscales o domicilio desactualizados de Tomates de Autor S.L. como cargador. | Baja | Alta | `[REQUIERE CONFIRMACIÓN]` | Entidad centralizada `ConfiguracionCargador` editable por un usuario administrador. |
| **RSK-08** | Técnico | Caída de red o rechazo del servidor SMTP al enviar el correo con el DeCA al transportista. | Media | Media | **RESUELTO (ADR-010)** | Envío desacoplado de la emisión del DeCA. El fallo genera estado `EMAIL_FAILED` y botón de reintento. |
| **RSK-09** | Legal | Discrepancia sobre el plazo de custodia interna obligatoria (transporte vs. fiscal/mercantil). | Baja | Media | `[LEGAL_REVIEW_REQUIRED]` | Custodia configurada por defecto a $\ge 1\text{ año}$ por transporte, parametrizable a 5 años si asesoría lo exige. |
| **RSK-10** | Integración | Dificultad para conectar en el futuro la API directa de Hispatec. | Baja | Media | **RESUELTO (ADR-005)** | Interfaz abstracta `DocumentImporter` que produce un `ShipmentDraft` neutral independiente del formato. |
| **RSK-11** | Operativa | Desincronización o confusión de expediciones en muelle por referencias externas ausentes o variables. | Media | Alta | **RESUELTO (ADR-011)** | Generador atómico de identificadores visibles y legibles `TD-YYYY-NNNNN` asignados en la importación. |
| **RSK-12** | Fiscal / Legal | Datos fiscales incompletos de Cultivos Araba S.L. (NIF o domicilio fiscal ausentes en sistema). | Alta | Alta | `[REQUIERE CONFIGURACIÓN]` | Entidad `Company` con `is_fully_configured = False` y `pending_fields`. No invención de datos. Bloqueo de emisión hasta configuración administrativa. |
| **RSK-13** | Seguridad | Contaminación cruzada o acceso no autorizado entre Tomates de Autor y Cultivos Araba (IDOR cross-company). | Media | Crítica | **RESUELTO (ADR-016)** | Aislamiento por `company_id`, claves de deduplicación segregadas, verificación `X-Company-Id` (403) y auditoría `UNAUTHORIZED_ACCESS_ATTEMPT`. |

---

## 3. DECISIONES PENDIENTES QUE REQUIEREN INTERVENCIÓN HUMANA

### 3.1. `[REQUIERE CONFIRMACIÓN]` (Datos de la Empresa y Operativa)
1. **Datos Fiscales Oficiales de Tomates de Autor S.L.:**
   - Razón Social exacta.
   - NIF / CIF definitivo.
   - Domicilio social completo.
2. **Muestras Documentales de Hispatec:**
   - 2 o 3 ejemplos reales anonimizados de albaranes / cartas de porte de Hispatec para afinar las expresiones regulares del parser.
3. **Proveedor de Correo Corporativo:**
   - Buzón y credenciales SMTP para pruebas (Microsoft 365 o Google Workspace).
4. **Datos Fiscales Oficiales de Cultivos Araba S.L. (`[REQUIERE CONFIGURACIÓN]`):**
   - NIF / CIF definitivo.
   - Domicilio fiscal completo.

### 3.2. `[LEGAL_REVIEW_REQUIRED]` (Asesoría Jurídica y Normativa)
1. **Procedimiento formal de registro de `fecha_fin_servicio`:**
   - Confirmar si la finalización del servicio la marcará el operador al recibir el acuse de entrega o si se habilita un mecanismo para que el transportista notifique la descarga.
2. **Plazo de custodia interna definitiva:**
   - Ratificar si la retención de los PDFs en el almacenamiento privado debe fijarse en 1 año (transporte) o en 5 años (prescripción tributaria).

### 3.3. `[TECH_DECISION_REQUIRED]` (Infraestructura y Sistemas)
1. **Destino de Despliegue Definitivo:**
   - Elección entre Google Cloud Run vs. VPS Linux corporativo (Hetzner / OVH) con Docker Compose. (No bloquea la implementación del código gracias a ADR-002).
2. **Subdominio Corporativo Oficial:**
   - Delegación DNS del subdominio para los códigos QR (ej: `https://deca.tomatesdeautor.com`).
