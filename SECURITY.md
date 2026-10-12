# DECA LIGHT — MODELO DE AMENAZAS Y SEGURIDAD (CONSOLIDADO)
**Proyecto:** DECA Light  
**Empresa:** Tomates de Autor S.L.  
**Versión:** 1.5  
**Fecha:** 03/10/2026  
**Estado:** Especificación de Seguridad Consolidada (Prompt 01.5)

---

## 1. PRINCIPIO DE SEGURIDAD POR DISEÑO

DECA Light se diseña con un enfoque de defensa en profundidad. La coexistencia obligatoria entre un endpoint público de inspección sin login y un panel administrativo privado para la gestión de albaranes exige una segregación arquitectónica rigurosa.

---

## 2. SEPARACIÓN ABSOLUTA: IDENTIFICADOR INTERNO VS. TOKEN PÚBLICO

Para evitar de raíz cualquier vulnerabilidad de referencia directa a objetos inseguros (IDOR) o raspado masivo de secretos comerciales:

```
┌────────────────────────────────────────────────────────┐
│                   PANEL ADMINISTRATIVO                 │
│              /admin/expediciones/{uuid}                │
│  - Requiere autenticación y sesión HTTP-Only / Secure  │
│  - Identificador: UUIDv4 interno                       │
└────────────────────────────────────────────────────────┘

                           ≠ (Sin relación directa)

┌────────────────────────────────────────────────────────┐
│               ENDPOINT PÚBLICO DE CONTROL              │
│                       /d/{token}                       │
│  - Sin autenticación (acceso para inspectores en ruta) │
│  - Token: 256 bits de entropía CSPRNG (Base64URL)      │
│  - Descarga binaria directa inmediata del PDF          │
│  - Rate Limiting: 30 req/min por IP                    │
│  - Cabeceras: X-Robots-Tag: noindex, nofollow          │
└────────────────────────────────────────────────────────┘
```

- **Imposibilidad de inferencia:** El token público (`secrets.token_urlsafe(32)`) no guarda ninguna relación matemática con el UUID interno, el número de albarán o la matrícula.
- **Espacio de claves inatacable:** Un espacio de búsqueda de $2^{256}$ combinaciones hace físicamente imposible la enumeración por fuerza bruta.

---

## 3. PROTECCIÓN DE CARGA DE ARCHIVOS Y DEFENSA CONTRA EXPLOITS PDF

1. **Validación de Bytes Mágicos:** Se descarta cualquier archivo cuya cabecera binaria real no comience por `%PDF-`, independientemente de la extensión que declare el usuario.
2. **Protección contra Path Traversal:** El nombre de archivo original recibido (`filename`) se sanea y se descarta para el almacenamiento en disco. El archivo físico se renombra internamente mediante su hash `SHA-256` y se guarda en un directorio fuera de la raíz web pública.
3. **Límite Estricto de Tamaño:** El servidor rechaza en cabecera cualquier payload superior a 15 MB (`HTTP 413 Payload Too Large`), previniendo ataques de agotamiento de memoria o denegación de servicio.
4. **Sandboxing de Parsers:** La extracción de texto se ejecuta sin privilegios de sistema operativo y sin habilitar soporte de JavaScript en el motor PDF.

---

## 4. IDEMPOTENCIA Y PROTECCIÓN CONTRA OPERACIONES DUPLICADAS

Se establecen 4 controles que impiden duplicaciones accidentales o intencionadas:
- **Archivo duplicado:** El cálculo de `SHA-256` previo a la escritura bloquea la re-importación del mismo fichero físico.
- **Expedición duplicada:** La clave de negocio `(cargador_nif, ejercicio, referencia_origen)` previene la duplicación de albaranes de Hispatec.
- **DeCA duplicado:** Relación 1:1 estricta en base de datos.
- **Email duplicado:** Clave única de idempotencia `SHA-256(version_deca_id + email)` en la tabla `envio_email`.

---

## 5. MATRIZ DE RIESGOS CLASIFICADA

| Nivel | Amenaza | Impacto | Mitigación Arquitectónica |
| :--- | :--- | :--- | :--- |
| **CRÍTICO** | Enumeración de URLs (IDOR) en endpoint público `/d/{token}`. | Fuga de datos de clientes y precios. | Tokens CSPRNG de 256 bits, Rate Limit por IP y cabeceras anti-indexación. |
| **CRÍTICO** | Subida de archivos maliciosos (PDF políglota / exploit de parser). | Ejecución remota o DoS del muelle. | Validación de Magic Bytes, límite de 15 MB y parser sin ejecución JS. |
| **ALTO** | Fuga de credenciales corporativas (SMTP / API keys). | Uso del correo para spam o suplantación. | Variables de entorno del sistema (`Twelve-Factor`); prohibido en Git y en BD. |
| **ALTO** | Pérdida de trazabilidad o borrado prematuro de DeCAs. | Sanciones en inspección de transporte. | Almacenamiento inmutable y retención legal obligatoria $\ge 1\text{ año}$. |
| **MEDIO** | Manipulación de cabeceras en envío de email (SMTP Injection). | Exfiltración de PDFs a terceros. | Sanitización rigurosa de retornos de carro (`\r\n`) en campos de correo. |
| **MEDIO** | Ataque XSS o CSRF en la interfaz operativa de muelle. | Secuestro de sesión del operario. | Autoescape estricto en Jinja2 y tokens CSRF obligatorios en formularios. |
| **BAJO** | Desincronización de reloj en metadatos del PDF. | Dudas en inspección sobre hora de emisión. | Servidor sincronizado por NTP y forzado a huso horario legal `Europe/Madrid`. |

---

## 6. GESTIÓN DE PRIVACIDAD (RGPD) Y RETENCIÓN

- **Minimización de datos personales:** Únicamente se tratan los datos exigidos por la Orden FOM/2861/2012. En el caso de transportistas autónomos, sus datos de contacto se procesan bajo la base jurídica de obligación legal (Art. 6.1.c RGPD).
- **Desactivación de URL pública:** Pasados 7 días naturales desde `fecha_fin_servicio`, el acceso público se desactiva devolviendo `410 Gone`.
- **Custodia interna:** El documento permanece en el repositorio interno privado para auditoría oficial durante al menos 1 año.
- **`[LEGAL_REVIEW_REQUIRED]`:** Ratificación del plazo de prescripción mercantil y fiscal (1 año vs. 5 años).

---

## 7. SECURITY REVIEW — FASE 6 (QR, TOKENS CRIPTOGRÁFICOS Y ACCESO PÚBLICO)

### 7.1. Modelo de Amenazas del Endpoint Público
El endpoint `/d/{token}` expone un servicio accesible sin autenticación para permitir la inspección de carretera por parte de las Fuerzas y Cuerpos de Seguridad del Estado y los transportistas. Esto introduce riesgos específicos evaluados y mitigados:

1. **Ataque de Enumeración / Fuerza Bruta (IDOR):**
   - *Amenaza:* Un atacante genera peticiones secuenciales o aleatorias intentando descubrir documentos de porte de otros clientes.
   - *Mitigación:* Se emplean 256 bits de entropía real (`secrets.token_urlsafe(32)` $\rightarrow$ ~43 caracteres base64url). El espacio de claves de $2^{256} \approx 1.15 \times 10^{77}$ combinaciones hace físicamente imposible el descubrimiento fortuito o por fuerza bruta.
   - *Timing & Error Uniformity:* Ante tokens no existentes, malformados, caducados o revocados, la respuesta es uniforme: `HTTP 404 Not Found` con mensaje idéntico. Cero fugas de existencia o antigüedad.

2. **Ataques de Inyección SQL y Path Traversal:**
   - *Amenaza:* Inyección de payloads SQL (`' OR '1'='1`) o secuencias de escape (`../../etc/passwd`) en el parámetro `{token}`.
   - *Mitigación:* Validación sintáctica estricta con expresión regular `^[A-Za-z0-9_-]{32,128}$` antes de consultar cualquier capa de persistencia o almacenamiento. Búsqueda desacoplada mediante hash SHA-256 binario de 64 caracteres hex.

3. **Exposición de Secretos en Base de Datos y Backups:**
   - *Amenaza:* Una fuga o acceso indebido a una copia de seguridad expone los tokens públicos en claro.
   - *Mitigación:* La base de datos únicamente almacena `public_token_hash = sha256(token)`. Conocer el hash no permite reconstruir el token gracias a la resistencia a preimagen de SHA-256.

4. **Fuga de Información en Logs y Observabilidad:**
   - *Amenaza:* Los tokens o las URLs completas quedan expuestas en herramientas de agregación de logs (Datadog, CloudWatch, ELK).
   - *Mitigación:* Enmascaramiento activo en todos los eventos de auditoría (`f"{token[:6]}...{token[-4:]}"`). `SensitiveDataFilter` en el pipeline de logging intercepta y sustituye cualquier patrón de token antes de la serialización.

5. **Indexación y Caché en Proxies / Motores de Búsqueda:**
   - *Amenaza:* Indexación del documento por Googlebot o almacenamiento en proxies intermedios/CDN.
   - *Mitigación:* Cabeceras obligatorias en toda respuesta HTTP:
     - `Cache-Control: private, no-cache, no-store, must-revalidate`
     - `X-Content-Type-Options: nosniff`
     - `X-Robots-Tag: noindex, nofollow, noarchive`

6. **Mitigaciones Pendientes a Nivel Infraestructura (Fase 10):**
   - *Reverse Proxy Rate Limiting:* Configuración de Nginx / Cloudflare para limitar a 10 req/min por IP en `/d/` con `limit_req_status 429`.
   - *TLS 1.3 Forzado:* Exigencia de HTTPS exclusivo con HSTS preloaded en producción.

---

## 8. SECURITY REVIEW — FASE 7 (MICROSOFT GRAPH API, CREDENCIALES, MÍNIMO PRIVILEGIO Y PRIVACIDAD)

### 8.1. Principio de Mínimo Privilegio (Azure Entra ID & Exchange Online)
El permiso `Mail.Send` a nivel de aplicación (rol de aplicación sin usuario interactivo) otorga potencialmente la capacidad de enviar correos como cualquier buzón del tenant corporativo. Para mitigar este riesgo de elevación de privilegios:
- **Application Access Policy en Exchange Online:** Es de obligado cumplimiento configurar una política de alcance (`New-ApplicationAccessPolicy`) que limite estrictamente a la aplicación de Entra ID para enviar **únicamente desde `pedidos@tomatesdeautor.com`**. Cualquier intento de suplantar otro buzón (ej. dirección, administración) es rechazado en origen por los servidores de Microsoft con HTTP 403 Forbidden.
- **Sin Permisos de Lectura:** La aplicación NO posee permisos `Mail.Read`, `Mail.ReadWrite`, `User.Read.All` ni acceso a buzones de entrada, calendarios o archivos OneDrive/SharePoint.

### 8.2. Gestión de Credenciales y Secreto Cero en Código
- **Cero Secretos en Repositorio:** Ni `MS_GRAPH_TENANT_ID`, `MS_GRAPH_CLIENT_ID` ni `MS_GRAPH_CLIENT_SECRET` se almacenan en el código fuente, archivos de configuración versionados o imágenes Docker.
- **Inyección por Entorno:** Las credenciales se inyectan en tiempo de ejecución a través de gestores de secretos (Docker Secrets, Vault, variables de entorno de producción).
- **Aislamiento en Tests:** Toda la suite de pruebas unitarias y de integración se ejecuta en modo 100% offline mediante `FakeMicrosoftGraphEmailSender` y transporte mock de `httpx`, impidiendo llamadas accidentales o fugas de red hacia Microsoft.

### 8.3. Prevención de Ataques de Exfiltración (Recipient Tampering)
- **Bloqueo de Inyección de Destinatarios:** El endpoint `POST /api/v1/expeditions/{id}/deca/email` no acepta campos de destinatario (`recipient`, `to`, `destinatario`) en el cuerpo JSON de la petición.
- **Origen Estricto de Datos:** La dirección de envío se obtiene exclusivamente de la entidad de dominio validada (`expedition.carrier_email`), impidiendo que un atacante utilice la API para exfiltrar documentos DeCA confidenciales hacia correos externos no autorizados.

### 8.4. Verificación Criptográfica de Integridad Binaria Previa al Envío
- **Ataque de Alteración Custodial / TOCTOU:** Si un atacante o fallo de disco modifica los bytes del PDF en el directorio de almacenamiento antes del envío:
- **Control Pre-Flight:** El caso de uso calcula obligatoriamente el hash `SHA-256(pdf_bytes)` y lo compara con el `version.pdf_sha256` registrado de forma inmutable en el snapshot.
- **Aborto Inmediato:** Ante cualquier discrepancia, la transmisión se cancela de inmediato (`PDF_INTEGRITY_ERROR`), se marca el estado `EMAIL_FAILED`, se genera una alerta en la auditoría y **cero bytes son transmitidos al transportista**.

### 8.5. Privacidad y Cumplimiento RGPD en Observabilidad
- **Enmascaramiento Obligatorio:** Las direcciones de correo de los transportistas (personas físicas o autónomos) se consideran datos de carácter personal bajo el RGPD. El Value Object `EmailAddress` aplica ofuscación determinista (`jo***@domain.com`).
- **Sanitización de Trazas:** En todos los logs del sistema y en los registros de auditoría persistidos, el correo del destinatario figura enmascarado (`recipient_masked`).
- **Ocultamiento de Tokens y Cabeceras:** El adaptador `MicrosoftGraphEmailSender` nunca vuelca cabeceras `Authorization: Bearer ...` ni tokens de acceso en mensajes de log o excepciones devueltas a la capa de presentación.

---

## 9. SEGURIDAD MULTIEMPRESA Y CONTROL DE ACCESO CROSS-TENANT (PROMPT 7.5)

### 9.1. Prevención de IDOR Cross-Company en Endpoints Internos
En una arquitectura donde coexisten **Tomates de Autor S.L.** y **Cultivos Araba S.L.** sobre el mismo almacén de datos:
- **Cabecera `X-Company-Id`:** Los endpoints de expediciones (`/api/v1/expeditions/*`) y emisión/envío de DeCA (`/api/v1/deca/*`, `/api/v1/expeditions/{id}/deca/email`) validan la pertenencia societaria del recurso solicitado.
- **Respuesta 403 Forbidden y Auditoría Inmediata:** Si un operador o cliente contextualizado en una empresa intenta acceder, modificar vehículos, emitir DeCA o enviar correos de una expedición perteneciente a otra empresa, la petición es rechazada de inmediato con `HTTP 403 Forbidden`. Se registra de forma append-only un evento de auditoría `UNAUTHORIZED_ACCESS_ATTEMPT` con IP cliente, empresa solicitada y empresa real.

### 9.2. Inmutabilidad del Remitente de Correo y Prevención de Suplantación
- **Buzón Unificado:** Ambas sociedades envían desde la cuenta corporativa `pedidos@tomatesdeautor.com`.
- **Prohibición de Manipulación:** La API no acepta parámetros para alterar el remitente (`sender`, `from_email`). La firma y la razón social en el cuerpo se derivan estrictamente de la sociedad emisora asignada a la expedición (`expedition.company_id`).

### 9.3. Integridad Fiscal y No Invención de Datos
- **Aislamiento Fiscal:** El sistema prohíbe terminantemente atribuir el NIF o la dirección de Tomates de Autor a Cultivos Araba.
- **Estado Bloqueante:** Si una empresa carece de datos fiscales requeridos, se declara con `is_fully_configured = False` y se reportan sus `pending_fields`. Ante cualquier documento con cargador no identificado de forma fidedigna, el sistema lo deriva a `PENDIENTE_REVISION` sin inferir empresas por defecto.

### 9.4. Endpoint Público Efímero Agnóstico a la Sociedad
- **Inspección en Carretera Sin Fricción:** El endpoint `/d/{token}` atiende inspecciones de DeCAs emitidos por cualquiera de las dos empresas sin exigir cabeceras societarias ni exponer previamente a qué empresa pertenece el documento, preservando la máxima confidencialidad comercial hasta la presentación legítima del PDF.


