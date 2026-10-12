# Guía de Configuración e Integración: Microsoft Graph API & Microsoft 365
## DECA Light — Envío Transaccional de DeCA vía `pedidos@tomatesdeautor.com`

---

## 1. Resumen Ejecutivo y Arquitectura

DECA Light utiliza **Microsoft Graph API v1.0** para la transmisión transaccional de los documentos de control administrativo (DeCA) en formato PDF vectorial a los transportistas.

La comunicación se realiza mediante el flujo seguro **OAuth 2.0 Client Credentials Grant** (autenticación servidor a servidor sin intervención humana interactiva), actuando en nombre del buzón corporativo autorizado:
`pedidos@tomatesdeautor.com`

```
┌─────────────────┐       OAuth 2.0 Token        ┌─────────────────────────┐
│                 │ ───────────────────────────> │   Azure Entra ID        │
│   DECA Light    │ <─────────────────────────── │  (Microsoft Identity)   │
│  (Docker / API) │        Bearer JWT            └─────────────────────────┘
│                 │
│                 │      POST /sendMail (PDF)    ┌─────────────────────────┐
│                 │ ───────────────────────────> │   Microsoft Graph v1.0  │
│                 │ <─────────────────────────── │  (pedidos@tomates...)   │
└─────────────────┘       202 Accepted           └───────────┬─────────────┘
                                                             │ SMTP M365
                                                             ▼
                                                 ┌─────────────────────────┐
                                                 │ Email del Transportista │
                                                 └─────────────────────────┘
```

---

## 2. Aprovisionamiento en Azure Entra ID (Paso a Paso para IT / DevOps)

### Paso 1: Registro de la Aplicación en Entra ID
1. Iniciar sesión en el portal de [Microsoft Entra Admin Center](https://entra.microsoft.com/) con privilegios de **Administrador Global** o **Administrador de Aplicaciones**.
2. Navegar a **Identidad > Aplicaciones > Registros de aplicaciones**.
3. Hacer clic en **+ Nuevo registro**.
4. Cumplimentar los campos:
   - **Nombre:** `DECA-Light-Transactional-Mailer`
   - **Tipos de cuenta admitidos:** *Solo cuentas de este directorio organizativo (Tomates de Autor S.L. - inquilino único)*.
   - **URI de redirección:** Dejar en blanco (no aplica para servicios demonio sin UI de login de usuario).
5. Hacer clic en **Registrar**.

### Paso 2: Obtención de Identificadores
En la vista general de la aplicación registrada, copiar y custodiar:
- **Id. de directorio (inquilino / tenant):** `MS_GRAPH_TENANT_ID` (GUID).
- **Id. de aplicación (cliente / client):** `MS_GRAPH_CLIENT_ID` (GUID).

### Paso 3: Generación del Secreto de Cliente (*Client Secret*)
1. En el menú lateral de la app, entrar a **Certificados y secretos > Secretos de cliente**.
2. Hacer clic en **+ Nuevo secreto de cliente**.
3. **Descripción:** `DECA-Light-Mailer-Prod-2026`
4. **Expiración:** 6 meses / 12 meses (según política interna de rotación).
5. Hacer clic en **Agregar**.
6. **Copiar inmediatamente el `Valor`** del secreto (no el Id. de secreto). Este valor solo se muestra una vez: `MS_GRAPH_CLIENT_SECRET`.

### Paso 4: Configuración de Permisos de API (*Application Permissions*)
1. En el menú lateral, seleccionar **Permisos de API > + Agregar un permiso**.
2. Elegir **Microsoft Graph**.
3. Seleccionar **Permisos de aplicación** (*Application permissions*, NO permisos delegados).
4. Buscar y marcar:
   - `Mail.Send` (Permite enviar correo como cualquier usuario en el buzón definido).
5. Hacer clic en **Agregar permisos**.
6. **MUY IMPORTANTE:** Hacer clic en **Conceder consentimiento de administrador para Tomates de Autor S.L.** (*Grant admin consent*). El estado debe mostrar un círculo verde verificado.

---

## 3. Principio de Mínimo Privilegio: Application Access Policy

Por defecto, el permiso `Mail.Send` a nivel de aplicación permite enviar desde cualquier buzón del tenant. Para restringir estrictamente el envío **únicamente y exclusivamente** desde `pedidos@tomatesdeautor.com`, el equipo de sistemas debe aplicar una directiva de acceso a nivel de Exchange Online mediante PowerShell:

```powershell
# 1. Conectar a Exchange Online PowerShell V3
Connect-ExchangeOnline -UserPrincipalName admin@tomatesdeautor.com

# 2. Crear un grupo de seguridad de correo si no existe
New-DistributionGroup -Name "DECA-Light-Allowed-Mailboxes" `
    -Type "Security" `
    -Members "pedidos@tomatesdeautor.com"

# 3. Crear la Application Access Policy vinculada a la App de Entra ID
New-ApplicationAccessPolicy -AppId "<MS_GRAPH_CLIENT_ID>" `
    -PolicyScopeGroupId "DECA-Light-Allowed-Mailboxes@tomatesdeautor.com" `
    -AccessRight RestrictAccess `
    -Description "Restringe DECA Light para enviar exclusivamente desde pedidos@tomatesdeautor.com"

# 4. Verificar la política
Test-ApplicationAccessPolicy -AppId "<MS_GRAPH_CLIENT_ID>" `
    -Identity "pedidos@tomatesdeautor.com"
# Salida esperada: AccessCheckResult: Granted

Test-ApplicationAccessPolicy -AppId "<MS_GRAPH_CLIENT_ID>" `
    -Identity "direccion@tomatesdeautor.com"
# Salida esperada: AccessCheckResult: Denied
```

---

## 4. Variables de Entorno en DECA Light

En el archivo `.env` del servidor o en el gestor de secretos (Docker Secrets, GCP Secret Manager, Vault):

```env
# Proveedor de correo: "graph" para producción/staging M365, "stub" o "fake" para tests
EMAIL_PROVIDER=graph

# Azure Entra ID / Microsoft Graph Credentials
MS_GRAPH_TENANT_ID=00000000-0000-0000-0000-000000000000
MS_GRAPH_CLIENT_ID=11111111-1111-1111-1111-111111111111
MS_GRAPH_CLIENT_SECRET=tu-secreto-seguro-obtenido-del-portal
MS_GRAPH_SENDER_EMAIL=pedidos@tomatesdeautor.com
```

> [!WARNING]
> **REGLA DE SEGURIDAD ABSOLUTA:**
> Nunca comitees `.env` con credenciales reales a Git. En CI/CD y tests locales automáticos, DECA Light utiliza `EMAIL_PROVIDER=stub` o `EMAIL_PROVIDER=fake`, operando 100% aislado sin conexión a Azure.

---

## 5. Idempotencia y Ciclo de Vida del Envío

1. **Clave de Idempotencia Canónica:**
   $$\text{IdempotencyKey} = \text{SHA256}(\text{AUTO}:\text{deca\_id}:\text{version\_number}:\text{carrier\_email}:\text{pdf\_sha256})$$
   Garantiza matemáticamente que una re-ejecución no duplica el correo si el estado anterior fue `EMAIL_SENT`.

2. **Reenvío Manual Forzado:**
   Si el transportista solicita explícitamente una retransmisión, el operador usa `force_resend=True`, generando una clave diferenciada con timestamp y registrando el evento de auditoría `EMAIL_RESEND_REQUESTED`.

3. **Verificación de Integridad Binaria:**
   Antes de llamar a Microsoft Graph, el caso de uso recupera el PDF de custodia y comprueba:
   $$\text{SHA256}(\text{pdf\_bytes}) == \text{version.pdf\_sha256}$$
   Si difiere: **cero transmisión**, estado `EMAIL_FAILED`, error `PDF_INTEGRITY_ERROR`.

4. **Inmutabilidad del DeCA ante Caídas de Red:**
   Si Microsoft Graph devuelve error (429, 500, timeout), la expedición permanece en `DECA_GENERADO` (no transiciona a `ENVIADA`), y el documento DeCA **permanece válido e inalterado**.

---

## 6. Procedimiento de Rotación de Credenciales

1. Crear un nuevo Client Secret en Entra ID antes de que expire el anterior (por ejemplo, con 15 días de margen).
2. Actualizar el valor `MS_GRAPH_CLIENT_SECRET` en el entorno o gestor de secretos de DECA Light.
3. Reiniciar el servicio contenedor de la API:
   ```bash
   docker compose restart deca-api
   ```
4. Verificar el funcionamiento emitiendo un envío de prueba controlado.
5. Eliminar el secreto antiguo en el portal de Azure Entra ID tras verificar la estabilidad.
