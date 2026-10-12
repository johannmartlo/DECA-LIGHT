# DECA LIGHT — ARQUITECTURA DEL SISTEMA (CONSOLIDADA)
**Proyecto:** DECA Light  
**Empresa:** Tomates de Autor S.L.  
**Versión:** 1.5 (Revisión y Consolidación de Arquitectura)  
**Fecha:** 03/10/2026  
**Estado:** Aprobada para Implementación

---

## 1. RESUMEN EJECUTIVO Y PRINCIPIOS DE DISEÑO

DECA Light es una aplicación operativa complementaria y ligera para **Tomates de Autor S.L.** que automatiza la emisión, validación, entrega por correo electrónico y custodia legal de los **Documentos Electrónicos de Control Administrativo (DeCA)** exigidos por la normativa de transporte de mercancías por carretera (Resolución de 5 de junio de 2026, BOE-A-2026-12784 y Orden FOM/2861/2012).

### Principios Fundamentales
1. **ERP primero, DECA Light después:** La empresa genera sus albaranes o cartas de porte en Hispatec antes de conocer la matrícula definitiva del vehículo. DECA Light interviene en el momento en que se conoce el transporte y se introduce la matrícula en muelle, sin bloquear la operativa del ERP.
2. **Infraestructura 100% agnóstica mediante Docker:** La aplicación se empaqueta en un contenedor OCI estándar y no depende de ningún proveedor específico. Podrá alojarse indistintamente en **Google Cloud Run, un VPS corporativo (Hetzner/OVH) o infraestructura local on-premise**. La decisión definitiva de hosting se aplaza sin generar deuda técnica.
3. **Extracción determinista sin IA para el núcleo:** Extracción de capas de texto nativo, reglas geométricas y cruce con maestros de transportistas. Cero alucinaciones, cero coste recurrente y latencia instantánea.
4. **DeCA Engine desacoplado del PDF:** El motor de negocio calcula un `DeCAEstructurado` agnóstico a partir de la expedición y el vehículo. Posteriormente, un componente `PdfRenderer` genera el PDF físico, permitiendo cambiar el diseño o la librería sin tocar el dominio.
5. **Design System alineado con CCO y App Logística:** Interfaz operativa con lenguaje visual SaaS moderno (inspiración en Linear, Stripe, Ramp, Mercury), optimizada para alta densidad informativa, atajos de teclado y respuesta inmediata.

---

## 2. ARQUITECTURA LIMPIA (HEXAGONAL) Y SEPARACIÓN DE CAPAS

La estructura garantiza que la lógica de negocio y las validaciones normativas no dependan de bases de datos, librerías gráficas, proveedores de email ni nubes concretas:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION                                  │
│   Web Admin UI (Jinja2 + HTMX / CCO Design) │ Public Endpoint (/d/{token})│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                          APPLICATION                                   │
│  Use Cases: ImportDocument, AssignVehicle, ValidateExpedition,         │
│             GenerateDeCA, DeliverDeCAEmail, QueryAuditTrail            │
│  DTOs: RawDocument, NormalizedDocument, DeCAEstructurado               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                             DOMAIN                                     │
│  Entities: Expedicion, DeCA, VersionDeCA, Transportista, Vehiculo      │
│  Value Objects: MatriculaRigido, MatriculaArticulado, NIF, DeCAToken    │
│  Domain Services: DeCAValidator, CarrierResolver, DeduplicationPolicy │
│  Domain Events: DocumentImported, VehicleAssigned, DeCAGenerated       │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │
┌───────────────────────────────────┴────────────────────────────────────┐
│                        INFRASTRUCTURE                                  │
│  - Importers: HispatecPdfImporter, CmrPdfImporter                      │
│  - Document Engine: ReportLabPdfRenderer, SegnoQrGenerator             │
│  - Storage: FilesystemStorageAdapter, S3CompatibleStorageAdapter       │
│  - Notification: SmtpEmailAdapter, Microsoft365EmailAdapter            │
│  - Persistence: SqlAlchemyRepository (PostgreSQL / SQLite WAL)         │
│  - Clock: SystemClock (NTP Europe/Madrid)                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. INFRAESTRUCTURA AGNÓSTICA (OCI / DOCKER)

Para evitar dependencias irreversibles (*vendor lock-in*), la aplicación se concibe como un **Monolito Modular empaquetado en Docker**:

- **Contenedor:** Base Linux ligera (`python:3.12-slim`), sin dependencias de sistemas operativos propietarios.
- **Configuración:** 100% inyectada vía variables de entorno (`Twelve-Factor App`).
- **Persistencia desacoplada:**
  - Base de datos relacional estándar mediante SQLAlchemy 2.0 (PostgreSQL en producción o SQLite en disco persistente).
  - Almacenamiento de archivos mediante abstracción `StorageService` (compatible con sistema de ficheros montado en disco o bucket S3/GCS).
- **Despliegue indistinto:** El mismo contenedor Docker podrá desplegarse en:
  1. Google Cloud Run (con Cloud Storage y Cloud SQL).
  2. VPS Linux corporativo con Docker Compose (PostgreSQL + MinIO/Volumen).
  3. Servidor On-Premise dentro de la red del almacén.

---

## 4. MODELADO DE VEHÍCULO: RÍGIDO VS. ARTICULADO

El modelo no trata el remolque como un campo opcional universal. Se establece una tipificación explícita que gobierna la validación legal:

```
                      ┌────────────────────────┐
                      │    TIPO DE VEHÍCULO    │
                      └───────────┬────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         │                                                 │
┌────────▼───────────────┐                       ┌─────────▼──────────────┐
│    VEHÍCULO RÍGIDO     │                       │  CONJUNTO ARTICULADO   │
├────────────────────────┤                       ├────────────────────────┤
│ Matrícula Vehículo:    │                       │ Matrícula Tractor:     │
│   OBLIGATORIA          │                       │   OBLIGATORIA          │
│ Matrícula Remolque:    │                       │ Matrícula Semirremolque│
│   PROHIBIDA / NO APLICA│                       │   OBLIGATORIA          │
└────────────────────────┘                       └────────────────────────┘
```

### Reglas del Validador de Negocio (`DeCAValidator`):
- **Si `tipo_vehiculo == RIGIDO`:** Se exige `matricula_vehiculo` (formato español o internacional normalizado). El campo `matricula_remolque` debe ser nulo.
- **Si `tipo_vehiculo == ARTICULADO`:** Se exige obligatoriamente tanto `matricula_tractor` como `matricula_remolque`. No se permite emitir un DeCA para un camión articulado sin la matrícula de la caja/semirremolque de carga.

---

## 5. CICLO DE VIDA, VIGENCIA Y EXPIRACIÓN DETERMINISTA DEL QR

Se eliminan por completo estimaciones arbitrarias de duración del transporte (ej. reglas geográficas España/Francia). El sistema se rige por eventos deterministas:

1. **Emisión del DeCA (`fecha_inicio_servicio`):** Fecha y hora formal del inicio del servicio (previo a la marcha del vehículo). La URL pública queda inmediatamente **ACTIVA**.
2. **Durante el Transporte:** Mientras el servicio esté en curso, `fecha_fin_servicio` permanece `NULL`. La URL pública `/d/{token}` se mantiene permanentemente **DISPONIBLE** para inspectores en carretera.
3. **Finalización del Transporte (`fecha_fin_servicio`):**
   - Cuando se registra la finalización del servicio, se calcula de forma exacta:
     $$\text{expira\_descarga\_publica\_at} = \text{fecha\_fin\_servicio} + 7\text{ días naturales}$$
   - Superada esa fecha exacta, el endpoint `/d/{token}` devuelve `410 Gone`.
4. **Custodia Legal Obligatoria ($\ge 1\text{ año}$):** La desactivación pública no afecta al almacenamiento interno. El PDF y sus registros de auditoría se conservan en el repositorio privado durante el plazo legal obligatorio.

---

## 6. PIPELINE DE EXTRACCIÓN Y PARSER DESACOPLADO

El núcleo de dominio nunca procesa PDFs binarios directamente. El pipeline procesa el documento en fases estancas:

```
┌──────────────────┐
│ DocumentImporter │ -> Lee bytes del fichero (PDF Hispatec o CMR)
└────────┬─────────┘
         │
┌────────▼─────────┐
│   RawDocument    │ -> Texto plano extraído, coordenadas de layout y metadatos
└────────┬─────────┘
         │
┌────────▼─────────┐
│     Parser       │ -> Aplica reglas deterministas y regex según formato
└────────┬─────────┘
         │
┌────────▼─────────┐
│NormalizedDocument│ -> Fechas ISO, NIFs mayúsculas, pesos en kg flotante
└────────┬─────────┘
         │
┌────────▼─────────┐
│    Expedition    │ -> Entidad de dominio en estado PENDIENTE_MATRICULA
└──────────────────┘
```

- Si el documento no coincide con ningún formato conocido o su índice de certeza es insuficiente, se marca como `NEEDS_REVIEW` para revisión humana.
- **IA y OCR:** No forman parte del flujo nuclear del MVP.

---

## 7. MOTOR DECA (DECA ENGINE) & PDF RENDERER

Se establece una estricta separación de responsabilidades:

1. **`DeCAEngine` (Dominio):**
   $$\text{Expedicion} + \text{Vehiculo (Validado)} + \text{ConfiguracionCargador} \longrightarrow \mathbf{DeCAEstructurado}$$
   - El `DeCAEstructurado` es un Value Object inmutable que contiene todos los datos validados conforme a la Orden FOM/2861/2012 y la Resolución BOE-A-2026-12784.
2. **`PdfRenderer` (Infraestructura):**
   Recibe el `DeCAEstructurado` y el código QR generado por `Segno` y realiza el dibujo vectorial del PDF con `ReportLab`.
   - Generación nativa (vectorial, textos nítidos, tamaño $\le 300\text{ KB}$).
   - Estampado de metadatos PDF legales (`CreationDate`, `ModDate`, `Author`).

---

## 8. QR Y ENDPOINT PÚBLICO: SEGREGACIÓN ABSOLUTA

- **Endpoint de Administración (`/admin/*`):** Requiere autenticación de usuario, cookie de sesión segura, protección CSRF y control de acceso.
- **Endpoint Público de Inspección (`/d/{token}`):**
  - **Token opaco de 256 bits:** Generado con generador criptográfico CSPRNG (`secrets.token_urlsafe(32)`).
  - **Desacoplamiento total:** Es matemáticamente imposible inferir el ID interno de la expedición a partir del token, y viceversa.
  - **Descarga directa:** No contiene HTML, ni visores, ni botones intermedios. Devuelve directamente el flujo binario `application/pdf` con cabecera `Content-Disposition: inline; filename="DECA-XXXX.pdf"`.
  - **Seguridad:** Rate limiting por IP (30 req/min) y cabeceras `X-Robots-Tag: noindex, nofollow, noarchive`.

---

## 9. SISTEMA DE DISEÑO (DESIGN SYSTEM): ECOSISTEMA CCO & LOGÍSTICA

DECA Light se integra visualmente en el mismo lenguaje operativo que el **CCO** y la **aplicación logística de Tomates de Autor S.L.**, utilizando patrones visuales de herramientas SaaS de alto rendimiento (Linear, Stripe, Ramp, Mercury):

### Directrices de Experiencia de Usuario:
1. **Alta densidad informativa:** Tablas compactas con tipografía monoespaciada para matrículas, NIFs y números de albarán.
2. **Operación intensiva por teclado:**
   - Atajo `Ctrl + I` para importar documentos.
   - Navegación con flechas en la tabla de expediciones.
   - Foco automático inmediato en el input de matrícula al seleccionar una expedición en estado `PENDIENTE_MATRICULA`.
   - `Enter` para guardar matrícula; `Ctrl + Enter` para Validar y Emitir DeCA.
3. **Componentes visuales estandarizados:**
   - **Badges de estado:**
     - `PENDIENTE_MATRICULA`: Ámbar sutil (`bg-amber-50 text-amber-700 border-amber-200`).
     - `LISTA_PARA_DECA`: Azul operacional (`bg-sky-50 text-sky-700 border-sky-200`).
     - `DECA_GENERADO`: Verde esmeralda (`bg-emerald-50 text-emerald-700 border-emerald-200`).
     - `ENVIADA`: Púrpura sutil (`bg-purple-50 text-purple-700 border-purple-200`).
     - `ERROR / REVISION`: Rojo sobrio (`bg-rose-50 text-rose-700 border-rose-200`).
4. **Cero dashboards decorativos:** Pantalla única dividida en dos zonas:
   - Panel izquierdo / superior: Lista de expediciones de la jornada con filtros inmediatos.
   - Panel derecho / inferior: Ficha de trabajo rápido (completar matrícula, verificar transportista y botón de acción principal).

---

## 10. ESTRATEGIA DE IDEMPOTENCIA MULTINIVEL

Para impedir operaciones duplicadas accidentales:
1. **Idempotencia de Archivo:** Hash `SHA-256` del binario importado. Si se sube el mismo PDF dos veces, se ignora y se recupera la expedición original.
2. **Idempotencia de Negocio:** Clave única `(cargador_nif, ejercicio, referencia_origen)`. No se pueden crear dos expediciones para el mismo albarán en la misma campaña.
3. **Idempotencia de Emisión DeCA:** Cada expedición tiene una relación 1:1 con su registro `DeCA`. Para el MVP, no se permite generar un segundo DeCA independiente para la misma expedición.
4. **Idempotencia de Email:** Campo `idempotency_key` generado como `hash(version_deca_id, destinatario_email)`. El servicio de correo verifica si ya existe un envío exitoso con esa clave antes de conectar con el servidor SMTP.

---

## 11. ARQUITECTURA MULTIEMPRESA Y TENANT ISOLATION (PROMPT 7.5)

DECA Light soporta la operación diaria y concurrente de dos sociedades mercantiles del mismo grupo agroalimentario sobre la misma instancia de despliegue:
1. `TOMATES DE AUTOR S.L.` (`TOMATES_DE_AUTOR`)
2. `CULTIVOS ARABA S.L.` (`CULTIVOS_ARABA`)

### Principios de Aislamiento y Modelo Operativo
1. **Entidad `Company` en Dominio:**
   - Cada empresa posee identidad inmutable (`company_id`), razón social legal, NIF/CIF, domicilio fiscal y alias documentales.
   - Validación de completitud fiscal: si faltan datos fiscales (como ocurre actualmente con Cultivos Araba), la empresa se marca con `is_fully_configured = False` y `pending_fields` (`tax_id`, `fiscal_address`). El sistema nunca inventa datos fiscales ausentes.
2. **Detección Automática Determinista (`CompanyDetector`):**
   - Jerarquía estricta:
     - Prioridad 1: NIF/CIF del cargador en documento (Confianza: 1.0).
     - Prioridad 2: Razón social exacta normalizada (Confianza: 0.95).
     - Prioridad 3: Alias documentales configurados (Confianza: 0.85).
   - Ante discordancia entre NIF y razón social, o empresa no identificada, el documento transiciona a `PENDIENTE_REVISION` sin asumir ninguna empresa por defecto.
3. **Aislamiento en Deduplicación y Persistencia:**
   - La clave de deduplicación de negocio incorpora el identificador de empresa (`{company_id}:CMR:{ref}` o `{company_id}:CP_CARGO:{ejercicio}:{fecha}:{destino}:{peso}`), impidiendo falsos positivos entre ambas empresas.
   - Las entidades `Expedition`, `DeCA`, `DeCAEstructurado`, `AuditEvent` y `EmailDelivery` contienen `company_id`.
   - Invariante de Dominio: una expedición no puede avanzar a `LISTA_PARA_DECA`, `DECA_GENERADO` ni `ENVIADA` sin tener asignada una empresa emisora.
4. **Buzón Corporativo Unificado y Firma Dinámica:**
   - Ambas sociedades transmiten sus correos exclusivamente desde la cuenta autorizada en Microsoft 365: `pedidos@tomatesdeautor.com`.
   - Se prohíbe la alteración del remitente por parte del usuario o de la API.
   - La personalización se realiza dinámicamente en el cuerpo del correo (`Atentamente,\n{empresa.razon_social}`).
5. **Seguridad Cross-Tenant (Anti-IDOR) y Acceso Público:**
   - En la API operativa interna, la cabecera `X-Company-Id` verifica que la expedición pertenezca a la empresa consultada. Si hay discrepancia, se emite `HTTP 403 Forbidden` y se registra un evento de auditoría `UNAUTHORIZED_ACCESS_ATTEMPT`.
   - El endpoint público `/d/{token}` es agnóstico a la empresa y permite la inspección en carretera de DeCAs de cualquiera de las empresas sin requerir cabeceras ni autenticación.
