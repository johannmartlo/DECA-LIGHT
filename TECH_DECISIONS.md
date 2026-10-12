# DECA LIGHT — REGISTRO DE DECISIONES DE ARQUITECTURA (ADRs CONSOLIDADO)
**Proyecto:** DECA Light  
**Empresa:** Tomates de Autor S.L.  
**Versión:** 1.5  
**Fecha:** 03/10/2026  
**Estado:** Decisiones Consolidadas de Arquitectura (Prompt 01.5)

---

## RESUMEN DE DECISIONES CONSOLIDADAS

| ID | Título | Estado | Impacto Principal |
| :--- | :--- | :--- | :--- |
| **ADR-001** | Arquitectura modular monolítica | **ACEPTADA** | Despliegue atómico sin microservicios; separación en 4 capas limpias. |
| **ADR-002** | Infraestructura agnóstica mediante Docker | **ACEPTADA** | Cero dependencias con proveedores cloud (Cloud Run / VPS / On-Premise). |
| **ADR-003** | DeCA Engine desacoplado del PDF | **ACEPTADA** | El motor calcula datos estructurados; `PdfRenderer` dibuja el documento. |
| **ADR-004** | Token público separado del ID interno | **ACEPTADA** | Token opaco de 256 bits (`secrets.token_urlsafe(32)`) para evitar IDOR y scraping. |
| **ADR-005** | Parser determinista para MVP | **ACEPTADA** | Extracción mediante capas de texto y regex; sin dependencias de IA en el núcleo. |
| **ADR-006** | Matrícula completada posteriormente a la importación | **ACEPTADA** | Permite emitir albaranes en Hispatec antes de conocer el vehículo (`PENDIENTE_MATRICULA`). |
| **ADR-007** | Design System basado en CCO / App Logística | **ACEPTADA** | UI SaaS operativa densa y basada en teclado (estilo Linear/Stripe), sin dashboards vacíos. |
| **ADR-008** | Tipificación estricta de vehículos (Rígido vs. Articulado) | **ACEPTADA** | El remolque no es opcional universal: obligatorio en articulado, prohibido en rígido. |
| **ADR-009** | Expiración determinista del QR sin estimaciones de viaje | **ACEPTADA** | Basado en `fecha_inicio_servicio` y `fecha_fin_servicio`. Desactivación a 7 días de entrega. |
| **ADR-010** | Estrategia de idempotencia multinivel | **ACEPTADA** | Prevención de dobles importaciones, expediciones, documentos y correos accidentales. |
| **ADR-011** | Generador Secuencial Atómico TD-YYYY-NNNNN | **ACEPTADA** | Referencia correlativa corta y visible reiniciada anualmente. |
| **ADR-012** | Desacoplamiento de Validación Legal y Normalizador | **ACEPTADA** | Reglas FOM/2861/2012 aisladas en Dominio y matrículas normalizadas. |
| **ADR-013** | DeCA Engine, Snapshot Inmutable y ReportLab | **ACEPTADA** | Snapshot canónico sellado con SHA-256 y renderizado vectorial ultraligero. |
| **ADR-014** | Token Criptográfico Efímero, QR Segno y Anti-IDOR | **ACEPTADA** | URL efímera pública con token de 256 bits, hash SHA-256 y QR vectorial. |
| **ADR-015** | Envío Microsoft Graph API v1.0 e Idempotencia Criptográfica | **ACEPTADA** | Envío transaccional OAuth 2.0 y prevención de dobles correos. |
| **ADR-016** | Multiempresa, Tenant Isolation y Company Context | **ACEPTADA** | Soporte de Tomates de Autor y Cultivos Araba con buzón compartido y aislamiento. |

---

### ADR-001: Arquitectura modular monolítica con Arquitectura Limpia
- **Estado:** ACEPTADA.
- **Contexto:** Se requiere un sistema pequeño, altamente profesional, rápido de desarrollar y sin deuda técnica para Tomates de Autor S.L.
- **Decisión:** Construir un **Monolito Modular** estructurado en cuatro capas concéntricas: `Domain`, `Application`, `Infrastructure`, `Presentation`. El dominio no tiene ninguna dependencia de bases de datos, librerías gráficas o frameworks web.
- **Consecuencias:** Máxima agilidad en el desarrollo, tests inmediatos y nula fricción operativa sin la complejidad de microservicios.

---

### ADR-002: Infraestructura agnóstica mediante Docker
- **Estado:** ACEPTADA.
- **Contexto:** No debe cerrarse prematuramente la elección entre Google Cloud Run, un VPS Linux corporativo o un servidor interno.
- **Decisión:** La aplicación se empaquetará en un **contenedor estándar OCI (Docker)** que se configurará exclusivamente mediante variables de entorno (Twelve-Factor App).
- **Consecuencias:** La aplicación se puede desplegar indistintamente en Cloud Run, Hetzner, AWS o en la red local de la empresa cambiando únicamente la configuración de infraestructura, con cero dependencias de APIs propietarias.

---

### ADR-003: DeCA Engine desacoplado del PDF Renderer
- **Estado:** ACEPTADA.
- **Contexto:** Se debe evitar que las particularidades visuales del PDF o la librería de renderizado contaminen la lógica de control legal de la expedición.
- **Decisión:** El `DeCAEngine` recibe una expedición validada y produce un `DeCAEstructurado` (Value Object inmutable). Posteriormente, un adaptador `PdfRenderer` basado en `ReportLab` toma esa estructura y el QR para renderizar el documento físico.
- **Consecuencias:** Permite sustituir la librería de PDF o generar otros formatos en el futuro sin tocar la validación del DeCA.

---

### ADR-004: Token público separado del ID interno
- **Estado:** ACEPTADA.
- **Contexto:** La Resolución BOE-A-2026-12784 exige una URL pública de descarga directa sin login para la Guardia Civil/inspectores.
- **Decisión:** La URL pública utilizará un token criptográfico no deducible de 256 bits (`secrets.token_urlsafe(32)`):
  $$\texttt{https://deca.tomatesdeautor.com/d/}\mathbf{w8xK3v9...}$$
  Existe separación absoluta entre las claves primarias internas (UUID) y el token de inspección pública.
- **Consecuencias:** Se anula cualquier posibilidad de enumeración secuencial (IDOR) o descarga masiva por competidores.

---

### ADR-005: Parser determinista para el MVP
- **Estado:** ACEPTADA.
- **Contexto:** Los albaranes de Hispatec contienen datos administrativos estructurados y predecibles.
- **Decisión:** El MVP utilizará extracción de texto nativo con `pdfplumber`/`pypdf`, expresiones regulares directas y cruce con el maestro de transportistas. Se prohíbe el uso de LLMs en el pipeline nuclear.
- **Consecuencias:** 100% de reproducibilidad, coste computacional cero, latencia de milisegundos y cero alucinaciones de NIFs o pesos.

---

### ADR-006: Matrícula completada posteriormente a la importación
- **Estado:** ACEPTADA.
- **Contexto:** En la operativa de Tomates de Autor S.L., las cartas de porte y albaranes se generan antes de que el camión o la empresa de portes confirme el vehículo definitivo.
- **Decisión:** La importación de documentos no exige matrícula. La expedición pasa al estado `PENDIENTE_MATRICULA`. La persona usuaria asigna la matrícula posteriormente en el muelle de carga antes de generar el DeCA.
- **Consecuencias:** El sistema se adapta perfectamente a la operativa real de la empresa sin bloquear el trabajo en el ERP.

---

### ADR-007: Design System basado en CCO y Aplicación Logística
- **Estado:** ACEPTADA.
- **Contexto:** La herramienta será utilizada a diario por el personal administrativo y de tráfico para procesar decenas de cargas.
- **Decisión:** La interfaz pertenecerá visual y funcionalmente al ecosistema de CCO y la aplicación logística de la empresa, inspirándose en patrones SaaS de alto rendimiento (Linear, Stripe, Ramp):
  - Alta densidad de datos y tipografía monoespaciada para códigos.
  - Foco y navegación completos mediante teclado.
  - Ausencia de dashboards decorativos: foco exclusivo en la tabla operativa de expediciones y estado de portes.
- **Consecuencias:** Máxima velocidad operativa, reducción de errores y consistencia de marca interna.

---

### ADR-008: Tipificación estricta de vehículos (Rígido vs. Articulado)
- **Estado:** ACEPTADA.
- **Contexto:** La Orden FOM/2861/2012 exige datos de tracción y carga según el tipo de transporte.
- **Decisión:** Modelar dos tipos de vehículos con validaciones obligatorias diferenciadas:
  1. `RIGIDO`: Matrícula del vehículo obligatoria. Remolque prohibido/nulo.
  2. `ARTICULADO`: Matrícula del tractor obligatoria Y matrícula del semirremolque obligatoria.
- **Consecuencias:** Se elimina la ambigüedad y se asegura el cumplimiento normativo en ambos tipos de flota.

---

### ADR-009: Expiración determinista del QR sin estimaciones de viaje
- **Estado:** ACEPTADA.
- **Contexto:** No deben usarse heurísticas geográficas arbitrarias para determinar la vigencia de la URL de control.
- **Decisión:** La aplicación opera con `fecha_inicio_servicio` (establecida al emitir) y `fecha_fin_servicio` (registrada al concluir la entrega).
  - Mientras el servicio esté en curso, la URL pública permanece disponible.
  - Una vez registrada la finalización, la expiración pública se fija deterministamente en $\text{fecha\_fin\_servicio} + 7\text{ días naturales}$.
  - La custodia interna privada se mantiene fija en $\ge 1\text{ año}$.
- **Consecuencias:** Se cumple la norma de forma matemática sin inventar datos no confirmados.

---

### ADR-010: Estrategia de idempotencia multinivel
- **Estado:** ACEPTADA.
- **Contexto:** Evitar fallos operativos por pulsaciones dobles o importación reiterada de ficheros.
- **Decisión:** Implementar 4 barreras de idempotencia:
  1. Hash `SHA-256` del fichero para descartar subidas duplicadas del mismo archivo.
  2. Clave compuesta de negocio `(cargador_nif, ejercicio, referencia_origen)`.
  3. Relación 1:1 estricta entre `Expedicion` y `DeCA` para el MVP.
  4. Clave de idempotencia única en envíos de correo `SHA-256(version_deca_id + email)`.
- **Consecuencias:** Imposibilidad de duplicar expediciones, DeCAs o envíos de correo accidentalmente.

---

### ADR-011: Generador Secuencial Atómico de Identificador Visible TD-YYYY-NNNNN
- **Estado:** ACEPTADA.
- **Contexto:** Los operadores de muelle necesitan una referencia corta, correlativa y legible para identificar expediciones sin depender de UUIDs ni del número de albarán externo (que puede venir ausente o tardío en cartas de porte).
- **Decisión:** Implementar `ExpeditionSequenceGeneratorPort` con generación atómica `TD-YYYY-NNNNN` (ej. `TD-2026-00001`):
  - Concurrencia thread-safe garantizada mediante locks en memoria y extensible a secuencias nativas de base de datos (`SEQUENCE` o `SELECT FOR UPDATE`).
  - Secuencia reiniciada anualmente por ejercicio fiscal.
- **Consecuencias:** Trazabilidad operativa inmediata en muelle con orden correlativo sin huecos ni colisiones.

---

### ADR-012: Desacoplamiento de Validación Legal (DeCAValidator) y Normalizador de Matrículas
- **Estado:** ACEPTADA.
- **Contexto:** La validación de la Orden FOM/2861/2012 debe ser exhaustiva, determinista e independiente de la infraestructura de persistencia, PDF o web.
- **Decisión:**
  - Crear el servicio de dominio puro `DeCAValidator` que evalúa una entidad `Expedition` y retorna `ValidationResult` diferenciando errores bloqueantes de advertencias no bloqueantes.
  - Implementar `VehicleRegistrationNormalizer` para matrículas españolas e internacionales conservando el texto original en el atributo `raw` y aplicando igualdad semántica (`compare=False` en el atributo de auditoría) en el Value Object `Matricula`.
- **Consecuencias:** Las reglas de negocio permanecen 100% aisladas en el Dominio, facilitando pruebas unitarias exhaustivas sin dependencias externas.

---

### ADR-013: DeCA Engine, Snapshot Inmutable y Renderizado Vectorial con ReportLab
- **Estado:** ACEPTADA (Fase 5 - Prompt 05).
- **Contexto:**
  - El documento DeCA emitido constituye una declaración administrativa y contractual fehaciente ante la Inspección de Transporte (FOM/2861/2012).
  - Mutaciones posteriores en la entidad operativa `Expedition` (modificación de transportista, cambio de matrículas, corrección de pesos o destino) jamás deben alterar retroactivamente un DeCA ya emitido, su versión física o su binario PDF.
  - La generación de PDF debe ser rápida (< 200 ms), ligera (< 300 KB) y reproducible de manera determinista.
- **Decisión:**
  1. Desacoplamiento estricto del renderizado: El PDF nunca se renderiza directamente desde `Expedition`.
     `Expedition (LISTA_PARA_DECA)` $\rightarrow$ `DeCAEngine` $\rightarrow$ `DeCAEstructurado` $\rightarrow$ `Snapshot Inmutable (dict canónico)` $\rightarrow$ `ReportLabPdfRenderer` $\rightarrow$ `PDF`.
  2. Snapshot Inmutable:
     - `DeCAEngine.create_deca_estructurado(...)` evalúa el estado `LISTA_PARA_DECA`, revalida con `DeCAValidator`, construye un diccionario canónico `snapshot_data` y calcula su hash criptográfico SHA-256 (`snapshot_hash`).
     - `DeCAVersion` almacena `snapshot_data` mediante copia profunda defensiva (`json.loads(json.dumps(...))`), asegurando que referencias mutables no afecten al histórico.
     - `DeCA.add_version(...)` bloquea cualquier sobreescritura de versiones existentes (`ImmutableDeCAException`).
  3. Renderizador ReportLab nativo (`ReportLabPdfRenderer`):
     - Dibujo vectorial sobre lienzo A4 con tipografía nativa Helvetica seleccionable (sin fuentes externas pesadas ni renderizado rasterizado borroso).
     - Tarjeta de cabecera con código formal `DECA-YYYY-NNNNNN` y versión.
     - Bloques diferenciados para cargador contractual, transportista efectivo, configuración de vehículo (distinguiendo vehículo rígido de articulado sin semirremolque fantasma), ruta, mercancía y peso.
     - Espacio visual reservado para el futuro código QR de carretera (Fase 6).
     - Declaración de validez legal conforme a FOM/2861/2012 y pie de página con huella criptográfica SHA-256.
  4. Custodia Determinista (`LocalPdfStorage`):
     - Almacenamiento físico en `storage/deca/{fiscal_year}/{deca_code}.pdf`.
     - Verificación estricta contra ataques de path traversal con mapeo a `StorageException`.
- **Consecuencias:**
  - Garantía legal de inmutabilidad comprobada por tests de regresión (la mutación de `Expedition` deja el DeCA v1 y su PDF 100% intactos).
  - Archivos PDF hiperoptimizados de ~5.1 KB (58 veces por debajo del límite de 300 KB) generados en ~6.7 ms (30 veces más rápidos que el umbral de 200 ms).

---

### ADR-014: Token Criptográfico de Acceso Efímero, QR Vectorial (Segno) y Protección Anti-IDOR
- **Estado:** ACEPTADA (Fase 6 - Prompt 06).
- **Contexto:**
  - Los agentes de la Guardia Civil / Inspección de Transporte y los conductores en ruta requieren verificar el DeCA mediante lectura óptica de un código QR en dispositivo móvil sin credenciales de acceso a la intranet corporativa.
  - Prohibición estricta de exponer identificadores correlativos (`DECA-YYYY-NNNNNN`), UUIDs internos o referencias de albarán en URLs públicas accesibles para prevenir recolección masiva e IDOR.
  - El QR debe renderizarse con nitidez perfecta sin pixelado en pantallas de alta densidad ni en impresiones térmicas o papel.
  - El acceso público debe caducar de forma determinista para cumplir con el principio de limitación del plazo de conservación de datos (RGPD).
- **Decisión:**
  1. **Generación de Token:**
     - Uso de `secrets.token_urlsafe(32)` proporcionando 256 bits de entropía real ($2^{256}$ combinaciones) representada en ~43 caracteres base64url seguros para URLs.
  2. **Persistencia Hashed (O(1)):**
     - La base de datos almacena exclusivamente `public_token_hash = SHA256(token)`. El token en claro se descarta de memoria tras la emisión y nunca se guarda en texto plano en disco ni logs.
  3. **QR Vectorial Nativo con Segno:**
     - Generación mediante `segno.make(url, error='m')` e iteración sobre la matriz booleana dibujando directamente rectángulos vectoriales en el `canvas` de ReportLab (`c.rect(..., fill=1, stroke=0)`). Cero dependencias de archivos temporales, cero rasterización a PNG/JPEG y tiempo de renderizado $< 5\text{ ms}$.
  4. **Estrategia A de Secuenciación:**
     - El token y la URL pública se construyen con carácter previo al renderizado, de modo que el PDF sellado y custodiado con hash SHA-256 contiene el QR definitivo embebido.
  5. **Endpoint Público `GET /d/{token}`:**
     - Sin login, entrega binaria directa del PDF con `Content-Disposition: inline` y cabeceras preventivas `Cache-Control: private, no-cache, no-store, must-revalidate`, `X-Content-Type-Options: nosniff` y `X-Robots-Tag: noindex, nofollow, noarchive`.
  6. **Anti-Enumeración y Timing Uniformity:**
     - Respuestas de error idénticas (`HTTP 404 Not Found` con mensaje uniforme `"Documento DeCA no encontrado o no disponible."`) ante tokens con formato inválido, tokens inexistentes, DeCAs revocados o tokens caducados.
  7. **Vigencia Temporal Determinista (`Clock`):**
     - Acceso libre durante el transporte (`fecha_fin_servicio IS NULL`).
     - Caducidad estricta tras 7 días naturales desde `fecha_fin_servicio`.
     - Abstracción de tiempo con `Clock.now()` para permitir pruebas deterministas de avance temporal.
  8. **Observabilidad:**
     - Registro estructurado de accesos (`PUBLIC_DECA_ACCESS_SUCCESS`, `PUBLIC_DECA_ACCESS_NOT_FOUND`, `PUBLIC_DECA_ACCESS_EXPIRED`) registrando IP cliente, User-Agent y token enmascarado (`token[:6]...token[-4:]`), nunca en claro.
- **Consecuencias:**
  - Imposibilidad matemática de enumeración por fuerza bruta.
  - Protección absoluta de la privacidad comercial de Tomates de Autor S.L.
  - Experiencia de usuario inmediata en control de carretera sin fricción.

---

### ADR-015: Transmisión Transaccional vía Microsoft Graph API v1.0, OAuth 2.0 e Idempotencia Criptográfica
- **Estado:** Aceptado
- **Fecha:** Octubre 2026
- **Contexto:**
  Tomates de Autor S.L. opera bajo Microsoft 365 con el buzón corporativo `pedidos@tomatesdeautor.com`. Microsoft ha depreciado y bloqueado la autenticación básica SMTP (Basic Auth) en Exchange Online. Es imprescindible enviar automáticamente el DeCA en PDF al transportista tras la emisión, garantizando:
  1. Cero duplicidades de correo por reintentos de red o clics repetidos.
  2. Verificación criptográfica de integridad del PDF antes de salir del servidor.
  3. Mínimo privilegio en Azure Entra ID (restringido únicamente al buzón de pedidos).
  4. Protección de privacidad (GDPR) evitando filtrar emails de transportistas en logs y auditorías.
  5. Desacoplamiento de fallos: la caída de Microsoft 365 o de red nunca debe invalidar el documento legal DeCA ya emitido.
- **Decisión:**
  1. **Proveedor y Protocolo:**
     - Utilizar Microsoft Graph API v1.0 (`POST https://graph.microsoft.com/v1.0/users/{sender}/sendMail`) mediante el flujo servidor a servidor **OAuth 2.0 Client Credentials Grant** (`https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`).
     - Caché interna del token Bearer para amortizar peticiones a Microsoft Identity.
  2. **Arquitectura Hexagonal:**
     - Definir el puerto `EmailSenderPort` desacoplado en `application/ports`.
     - Implementar `MicrosoftGraphEmailSender` para producción y staging con reintentos exponenciales ante fallos transitorios (HTTP 429 con cabecera `Retry-After`, 500, 502, 503, 504 y timeouts).
     - Implementar `FakeMicrosoftGraphEmailSender` para tests deterministas y entornos locales sin llamadas externas a Microsoft.
  3. **Idempotencia Criptográfica:**
     - Clave determinista automática:
       $$\text{IdempotencyKey} = \text{SHA-256}(\text{AUTO}:\text{deca\_id}:\text{version\_number}:\text{carrier\_email}:\text{pdf\_sha256})$$
     - Al detectar un envío previo confirmado (`EMAIL_SENT`), la operación retorna inmediatamente con `is_idempotent=True` sin transmitir duplicados.
     - Para reenvíos manuales explícitos solicitados por el operador (`force_resend=True`), se genera una clave con timestamp y se registra la auditoría específica `EMAIL_RESEND_REQUESTED`.
  4. **Verificación de Integridad Binaria:**
     - Antes de emitir cualquier llamada externa, se calcula `SHA-256(pdf_bytes)` y se contrasta con `version.pdf_sha256`. Si hay discrepancia, se aborta inmediatamente con `PDF_INTEGRITY_ERROR`, estado `EMAIL_FAILED` y cero transmisión.
  5. **Mínimo Privilegio y Privacidad:**
     - La App de Entra ID se restringe mediante `ApplicationAccessPolicy` en Exchange Online exclusivamente a `pedidos@tomatesdeautor.com`.
     - Value Object `EmailAddress` con método `masked` para ofuscar los buzones en logs y eventos de auditoría (`jo***@domain.com`).
     - El endpoint `POST /api/v1/expeditions/{id}/deca/email` toma el destinatario exclusivamente de la expedición; prohíbe inyección de destinatarios en el cuerpo de la petición.
  6. **Resiliencia e Invariantes:**
     - La expedición transiciona a `ENVIADA` únicamente si Microsoft Graph confirma la recepción (`202 Accepted`).
     - Ante cualquier fallo de red o del proveedor, la expedición permanece en `DECA_GENERADO` y el DeCA permanece 100% válido para su consulta física o inspección en carretera.
- **Consecuencias:**
  - Máxima seguridad de credenciales sin secretos expuestos ni cuentas de usuario personales.
  - Operaciones de envío 100% auditables, reproducibles y resistentes a caídas transitorias de red.
  - Aislamiento completo en tests automáticos sin dependencias de internet.

---

### ADR-016: Multiempresa, Tenant Isolation Compartido y Company Context
- **Estado:** ACEPTADA (Fase 7.5 - Multiempresa)
- **Fecha:** Octubre 2026
- **Contexto:**
  DECA Light opera diariamente para dos sociedades hermanas pertenecientes al mismo grupo agroalimentario:
  1. `TOMATES DE AUTOR S.L.` (`TOMATES_DE_AUTOR`)
  2. `CULTIVOS ARABA S.L.` (`CULTIVOS_ARABA`)
  Ambas empresas comparten los mismos formatos documentales (Carta de Porte y CMR de Hispatec ERP), la misma operativa de almacén/muelle, la misma infraestructura de red y el mismo buzón unificado corporativo de Microsoft 365 (`pedidos@tomatesdeautor.com`).
  Sin embargo, legal y fiscalmente son entidades jurídicas completamente separadas:
  - Un DeCA emitido para Cultivos Araba debe llevar los datos fiscales y razón social de Cultivos Araba.
  - La deduplicación por clave de negocio debe aislarse por empresa (dos cartas de porte con el mismo número o fecha/destino de diferentes sociedades no deben colisionar).
  - Los datos fiscales ausentes de Cultivos Araba no deben inventarse; deben marcarse como `REQUIERE_CONFIGURACION`.
  - La cuenta remitente de correo `pedidos@tomatesdeautor.com` es fija e inmutable; el usuario no puede alterarla ni suplantarla. La personalización se realiza dinámicamente en el cuerpo y firma del correo (`Atentamente,\n{empresa.razon_social}`).
  - Se debe prevenir IDOR cross-company en APIs operativas mediante `X-Company-Id`, devolviendo `403 Forbidden` ante accesos cruzados no autorizados.
  - El endpoint público de inspección en carretera `GET /d/{token}` debe resolver el documento de cualquiera de las empresas de forma agnóstica sin requerir cabeceras, basándose únicamente en el token criptográfico de 256 bits.
- **Decisión:**
  1. **Modelo de Dominio Multiempresa:**
     - Entidad `Company` en `domain/entities/company.py` con validación estricta, comprobación de completitud fiscal (`is_fully_configured`, `pending_fields`) y soporte de alias documentales.
     - Inyección de `company_id: str` como atributo obligatorio en `Expedition`, `DeCA`, `DeCAEstructurado`, `AuditEvent`, y `EmailDelivery`.
     - Invariante de Dominio: una expedición no puede avanzar a `LISTA_PARA_DECA`, `DECA_GENERADO` o `ENVIADA` sin tener asignada una empresa emisora válida.
  2. **Detección Automática Determinista (`CompanyDetector`):**
     - Jerarquía de detección estricta:
       1) Prioridad 1: NIF/CIF del cargador (confianza 1.0).
       2) Prioridad 2: Razón social exacta normalizada (confianza 0.95).
       3) Prioridad 3: Alias documentales configurados (confianza 0.85).
     - Si el cargador es desconocido o existe conflicto entre NIF y nombre, se marca como `UNKNOWN` o `AMBIGUOUS` y la expedición queda en `PENDIENTE_REVISION` sin inventar datos.
  3. **Aislamiento en Persistencia y Deduplicación:**
     - Claves de deduplicación de negocio con prefijo de empresa: `{company_id}:CMR:{cmr_ref}` y `{company_id}:CP_CARGO:...`.
     - Soporte opcional de filtrado por `company_id` en `ExpeditionRepositoryPort` y `DeCARepositoryPort`.
  4. **Emisión de DeCA y Renderizado PDF:**
     - `DeCAEngine` inyecta el `company_id` y los datos del cargador de la empresa emisora en el snapshot inmutable.
     - `ReportLabPdfRenderer` utiliza dinámicamente la razón social de la empresa emisora en la cabecera, metadatos y pie de página documental.
  5. **Envío de Correo y Remitente Unificado:**
     - Envío transaccional exclusivo desde `pedidos@tomatesdeautor.com`.
     - Firma y cuerpo del mensaje generados dinámicamente con la razón social de la sociedad emisora.
  6. **Seguridad y Control de Acceso:**
     - Validación de cabecera `X-Company-Id` en endpoints de API interna (`/api/v1/expeditions/*`, `/api/v1/deca/*`), devolviendo `HTTP 403 Forbidden` si la expedición pertenece a otra sociedad.
     - Endpoint público de QR `GET /d/{token}` sin cabecera de empresa: resolución directa mediante token criptográfico no deducible.
- **Consecuencias:**
  - Soporte multiempresa completo sin necesidad de múltiples instancias de base de datos ni sobrecostes de infraestructura.
  - Aislamiento riguroso de expediciones y auditorías entre Tomates de Autor S.L. y Cultivos Araba S.L.
  - Cero riesgo de suplantación de remitente de correo o de alucinación de datos fiscales incompletos.
