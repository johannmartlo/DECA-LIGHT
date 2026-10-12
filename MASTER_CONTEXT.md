# DECA LIGHT — MASTER CONTEXT

**Proyecto:** DECA Light  
**Empresa objetivo:** Tomates de Autor S.L.  
**Versión:** 0.1  
**Fecha:** 03/10/2026  
**Estado:** Pre-desarrollo / Arquitectura inicial

---

# 1. PROPÓSITO DEL PROYECTO

DECA Light es una aplicación ligera destinada a facilitar y automatizar la generación, validación, almacenamiento y envío de los Documentos Electrónicos de Control Administrativo (DeCA) utilizados en el transporte de mercancías por carretera.

La aplicación NO pretende sustituir el ERP de la empresa.

Su objetivo es resolver específicamente la parte operativa del proceso DeCA que puede resultar poco ágil cuando la información de la expedición está disponible antes que la información definitiva del vehículo.

## Objetivo operativo principal

La persona encargada debería poder realizar, idealmente:

1. Exportar desde el ERP las cartas de porte / CMR.
2. Importarlas en DECA Light.
3. La aplicación identifica automáticamente las expediciones y extrae sus datos.
4. La persona introduce o confirma la matrícula del vehículo.
5. La aplicación valida los datos.
6. Genera el DeCA.
7. Genera el QR y la URL única.
8. Almacena el documento.
9. Envía el DeCA al transportista.
10. Registra la operación.

El objetivo es que el trabajo manual quede reducido al mínimo.

---

# 2. CONTEXTO OPERATIVO

Tomates de Autor S.L. es un almacén hortofrutícola que comercializa mercancía diariamente para sus clientes.

La empresa recibe pedidos y desarrolla su operativa habitual de:

PEDIDO → PREPARACIÓN/CARGA → ALBARÁN → CARTA DE PORTE / CMR → TRANSPORTE

En numerosas ocasiones, cuando se genera el albarán o carta de porte todavía no se conoce la matrícula definitiva del vehículo que realizará el transporte.

La información del vehículo puede llegar posteriormente, cuando la persona encargada de portes contacta con el transportista y solicita/asigna el transporte.

Por tanto:

**NO se debe diseñar el sistema obligando a bloquear la elaboración del albarán o carta de porte hasta conocer la matrícula.**

El DeCA debe generarse cuando los datos necesarios sean conocidos y, en todo caso, antes del inicio efectivo del servicio.

---

# 3. OBJETIVO DE DISEÑO

DECA Light debe ser:

- Rápido.
- Sencillo.
- Seguro.
- Accesible.
- Trazable.
- Fiable.
- Fácil de mantener.
- Fácil de desplegar.
- Fácil de ampliar.
- Con la mínima deuda técnica posible.

La aplicación debe estar diseñada para que una persona administrativa pueda utilizarla sin conocimientos técnicos.

---

# 4. PRINCIPIO FUNDAMENTAL

## ERP primero, DECA Light después

Antes de desarrollar una funcionalidad que ya pueda proporcionar el ERP/Hispatec, se debe comprobar si el ERP permite realizar correctamente el flujo.

DECA Light es una solución complementaria.

No debe duplicar innecesariamente funcionalidades ya disponibles.

La aplicación debe poder utilizar como fuente de entrada:

- PDF de carta de porte.
- PDF de CMR.
- CSV/Excel en el futuro.
- API de Hispatec en el futuro.

La arquitectura NO debe quedar acoplada exclusivamente al PDF.

---

# 5. FLUJO FUNCIONAL OBJETIVO

## Flujo básico

```text
ERP / HISPATEC
      |
      v
CARTA DE PORTE / CMR
      |
      v
IMPORTACIÓN DECA LIGHT
      |
      v
EXTRACCIÓN DE DATOS
      |
      v
NORMALIZACIÓN
      |
      v
IDENTIFICACIÓN TRANSPORTISTA
      |
      v
ASIGNACIÓN / INTRODUCCIÓN MATRÍCULA
      |
      v
VALIDACIÓN
      |
      v
GENERACIÓN DECA
      |
      +----> PDF
      |
      +----> QR
      |
      +----> URL HTTPS
      |
      +----> STORAGE
      |
      v
ENVÍO EMAIL
      |
      v
AUDITORÍA
```

---

# 6. PRINCIPIO DE AUTOMATIZACIÓN

La aplicación debe obtener automáticamente todo lo que pueda obtener de la documentación importada.

La persona usuaria NO debería tener que volver a introducir:

- cliente;
- cargador;
- NIF;
- origen;
- destino;
- mercancía;
- peso;
- fecha;
- transportista;
- email;

si esos datos ya están disponibles en el documento importado o pueden obtenerse de los maestros.

La persona usuaria debería introducir únicamente la información que realmente falte.

El caso habitual esperado será:

```text
Documento importado
        ↓
Datos identificados
        ↓
Transportista identificado
        ↓
Matrícula pendiente
        ↓
Usuario introduce matrícula
        ↓
VALIDAR
        ↓
GENERAR + ENVIAR
```

---

# 7. NO UTILIZAR IA COMO PRIMER MECANISMO DE EXTRACCIÓN

La extracción debe priorizar:

1. Texto estructurado del PDF.
2. Parser determinista.
3. Reglas de normalización.
4. Maestros de datos.
5. OCR únicamente cuando sea necesario.
6. IA como fallback futuro para documentos desconocidos o ambiguos.

NO utilizar un LLM como mecanismo principal para interpretar datos administrativos que pueden extraerse mediante reglas deterministas.

Los campos críticos deben estar sometidos a validación.

Ejemplo:

```text
610,41 kg
```

debe interpretarse de forma determinista.

No se debe confiar en que un modelo "interprete" el valor.

---

# 8. IMPORTADOR

El sistema debe disponer de una capa abstracta de importación.

Arquitectura conceptual:

```text
DocumentImporter
    |
    +-- PDFImporter
    |
    +-- CSVImporter       [futuro]
    |
    +-- ExcelImporter     [futuro]
    |
    +-- HispatecAPI       [futuro]
```

El resto del sistema debe trabajar con datos estructurados y NO directamente con PDFs.

Esto permitirá cambiar la fuente de datos sin rehacer el motor DeCA.

---

# 9. CARTA DE PORTE / CMR

La aplicación debe poder importar inicialmente:

- Carta de porte PDF generada por Hispatec.
- CMR PDF.

No asumir que todos los PDFs tienen exactamente la misma estructura.

Debe existir una estrategia de identificación de formato.

Ejemplo conceptual:

```text
PDF
 |
 +-- Formato Hispatec conocido
 |
 +-- CMR conocido
 |
 +-- Formato desconocido
```

Si el formato es desconocido:

```text
ESTADO = REVISIÓN NECESARIA
```

No generar automáticamente un DeCA con datos dudosos.

---

# 10. NORMALIZACIÓN

Los datos extraídos deben normalizarse antes de almacenarse.

Ejemplos:

### Matrícula

Normalizar:

```text
1234 abc
1234-ABC
1234 ABC
```

a una representación interna consistente.

### NIF

Eliminar espacios y normalizar mayúsculas.

### Razón social

Normalizar diferencias de:

```text
TRANSPORTES ABC SL
Transportes ABC S.L.
Transportes ABC, S.L.
```

para poder relacionarlas con el mismo transportista.

---

# 11. MAESTRO DE TRANSPORTISTAS

Debe existir una entidad Transportista.

Campos mínimos previstos:

```text
transportista_id
razon_social
nif
email_principal
activo
created_at
updated_at
```

Debe existir un sistema de aliases.

Ejemplo:

```text
Transportista:
Transportes ABC S.L.

NIF:
B12345678

Email:
portes@abc.es

Aliases:
TRANSPORTES ABC SL
TRANSPORTES ABC
ABC TRANSPORTES
```

Esto permitirá identificar transportistas aunque el documento no utilice exactamente la misma denominación del maestro.

---

# 12. VEHÍCULOS

Debe existir una entidad para vehículos.

Como mínimo:

```text
vehiculo_id
matricula
tipo
transportista_id
activo
created_at
updated_at
```

Debe contemplarse:

- matrícula de tractor;
- matrícula de remolque/semirremolque cuando corresponda.

No asumir que todos los transportes utilizan exactamente el mismo tipo de vehículo.

---

# 13. MODELO DE EXPEDICIÓN

Debe existir una entidad central que represente el servicio de transporte.

Conceptualmente:

```text
Expedicion
```

Debe poder relacionarse con:

- documento origen;
- carta de porte;
- CMR;
- cargador;
- transportista;
- origen;
- destino;
- mercancía;
- peso;
- fecha;
- vehículo;
- DeCA.

La aplicación no debe tratar el PDF como la entidad principal.

El PDF es una fuente documental.

La expedición es la entidad de negocio.

---

# 14. ESTADOS DE UNA EXPEDICIÓN

Estados iniciales previstos:

```text
IMPORTED
NEEDS_REVIEW
PENDING_VEHICLE
READY
DECA_GENERATED
SENT
ERROR
CANCELLED
```

El flujo habitual:

```text
IMPORTED
   ↓
PENDING_VEHICLE
   ↓
READY
   ↓
DECA_GENERATED
   ↓
SENT
```

Si falta información:

```text
NEEDS_REVIEW
```

---

# 15. VALIDACIÓN

Nunca debe generarse un DeCA incompleto.

Debe existir una capa independiente:

```text
DeCAValidator
```

La validación debe comprobar todos los campos legalmente necesarios antes de permitir la generación.

Si falta un dato:

```text
NO GENERAR
```

y mostrar exactamente qué falta.

Ejemplo:

```text
✓ Cargador
✓ NIF cargador
✓ Origen
✓ Destino
✓ Mercancía
✓ Peso
✓ Transportista
✓ NIF transportista
✗ Matrícula
```

Resultado:

> DeCA no puede generarse: falta matrícula del vehículo.

---

# 16. NORMATIVA DECA

Fuente normativa principal:

Resolución de 5 de junio de 2026, de la Dirección General de Transporte por Carretera y Ferrocarril.

BOE:
BOE-A-2026-12784

La resolución establece las características de los sistemas y documentos electrónicos de control administrativo (DeCA).

Fuente oficial:
https://www.boe.es/buscar/act.php?id=BOE-A-2026-12784

IMPORTANTE:

La normativa debe considerarse una fuente de requisitos técnicos y funcionales.

No inventar requisitos.

Cuando exista duda jurídica, marcar:

```text
LEGAL_REVIEW_REQUIRED
```

en lugar de asumir una interpretación.

---

# 17. REQUISITOS TÉCNICOS DEL DECA

El sistema debe contemplar:

- PDF.
- Tamaño máximo 5 MB.
- Generación nativa digital.
- Fecha/hora de creación como metadatos.
- Fecha/hora de modificación como metadatos cuando corresponda.
- QR incluido dentro del PDF.
- URL única y específica para cada documento.
- HTTPS.
- TLS 1.2 o superior.
- Descarga directa del PDF.
- Sin autenticación para la URL de inspección.
- Sin página intermedia.
- Sin botón manual de descarga.
- Disponibilidad durante el servicio.
- Posibilidad de desactivar la descarga de la URL transcurridos siete días naturales desde la finalización del servicio.
- Conservación de los ficheros durante al menos un año.

Fuente: Resolución BOE-A-2026-12784.

---

# 18. URL Y QR

Cada DeCA tendrá una URL única.

Ejemplo:

```text
https://deca.example.es/d/8F72A91C...
```

El QR debe apuntar a esa URL.

La llamada a la URL debe producir directamente la descarga del PDF.

NO crear:

```text
QR
 ↓
Página web
 ↓
Botón "Descargar"
```

Debe ser:

```text
QR
 ↓
URL HTTPS
 ↓
PDF
```

No utilizar Google Drive como arquitectura principal para este requisito salvo que se demuestre que cumple exactamente las condiciones exigidas.

Preferir un endpoint controlado por la aplicación.

---

# 19. REPOSITORIO

El sistema debe disponer de almacenamiento separado de la lógica de negocio.

Conceptualmente:

```text
Application
     |
     +---- Database
     |
     +---- Object Storage
```

El almacenamiento debe conservar los PDFs generados.

No depender exclusivamente de archivos locales.

Debe existir estrategia de:

- conservación;
- backup;
- control de acceso administrativo;
- integridad;
- auditoría.

---

# 20. VERSIONADO DEL DECA

Nunca sobrescribir silenciosamente un DeCA ya generado.

Debe existir versionado.

Ejemplo:

```text
DECA-2026-000125
    |
    +-- v1
    |
    +-- v2
```

Cada versión debe registrar:

```text
version
created_at
modified_at
created_by
reason
```

Cuando proceda un cambio de vehículo durante el servicio, utilizar el procedimiento de modificación previsto por la normativa.

La aplicación debe conservar la trazabilidad.

---

# 21. AUDITORÍA

Debe existir un registro de eventos.

Ejemplos:

```text
DOCUMENT_IMPORTED
DATA_EXTRACTED
DATA_CORRECTED
VEHICLE_ASSIGNED
VALIDATION_PASSED
DECA_CREATED
DECA_MODIFIED
DECA_SENT
EMAIL_FAILED
DECA_DOWNLOADED
```

Cada evento debe registrar como mínimo:

```text
timestamp
user/system
action
entity
entity_id
metadata
```

No guardar secretos en los logs.

---

# 22. DUPLICADOS

La aplicación debe detectar documentos importados anteriormente.

Ejemplo:

```text
Carta de porte 45821
```

importada dos veces:

```text
⚠ DOCUMENTO DUPLICADO
```

No generar automáticamente un segundo DeCA.

Debe existir una estrategia de idempotencia.

---

# 23. ENVÍO DE EMAIL

Crear una abstracción:

```text
EmailService
```

No acoplar el núcleo de la aplicación exclusivamente a Gmail.

Posibles implementaciones:

```text
EmailService
   |
   +-- Microsoft365
   |
   +-- Gmail
```

El envío debe registrar:

- destinatario;
- fecha/hora;
- DeCA;
- versión;
- resultado;
- error si existe.

Debe evitarse el envío duplicado accidental.

---

# 24. REINTENTOS DE EMAIL

Si falla el envío:

```text
EMAIL_FAILED
```

Debe ser posible reintentar.

No generar otro DeCA únicamente porque haya fallado el correo.

Separar:

```text
Generación del documento
```

de:

```text
Envío del documento
```

---

# 25. INTERFAZ DE USUARIO

La interfaz debe priorizar velocidad y simplicidad.

Pantalla principal ideal:

```text
┌────────────────────────────────────────────┐
│ DECA LIGHT                                │
├────────────────────────────────────────────┤
│                                            │
│ [ IMPORTAR CARTAS DE PORTE / CMR ]         │
│                                            │
├────────────────────────────────────────────┤
│ Expedición | Transportista | Matrícula     │
│                                            │
│ 45821      | Transportes A | [1234 ABC]   │
│ 45822      | Transportes B | [5678 DEF]   │
│ 45823      | Transportes A | [          ] │
│                                            │
├────────────────────────────────────────────┤
│ [ VALIDAR ] [ GENERAR ] [ ENVIAR ]        │
└────────────────────────────────────────────┘
```

No sobrecargar la interfaz.

---

# 26. ACCESIBILIDAD

La aplicación debe cumplir buenas prácticas de accesibilidad:

- navegación mediante teclado;
- labels claros;
- contraste suficiente;
- foco visible;
- mensajes de error comprensibles;
- no depender exclusivamente del color;
- botones suficientemente grandes;
- textos legibles;
- estructura semántica;
- compatibilidad con lectores de pantalla cuando sea viable.

Los estados deben comunicarse también mediante texto/iconos.

Ejemplo:

No utilizar solamente:

🔴

Utilizar:

```text
ERROR — Falta matrícula
```

---

# 27. SEGURIDAD

La seguridad es requisito desde el primer commit.

No dejar para el final.

Principios:

- mínimo privilegio;
- autenticación;
- autorización;
- secretos fuera del código;
- variables de entorno;
- validación de entrada;
- sanitización;
- control de archivos subidos;
- límite de tamaño;
- validación MIME;
- protección contra archivos maliciosos;
- protección contra inyección;
- rate limiting cuando proceda;
- logs de auditoría;
- backups;
- HTTPS;
- separación entre URL pública de inspección y panel administrativo.

IMPORTANTE:

La URL pública del DeCA debe ser accesible sin autenticación por requisito normativo durante el periodo correspondiente.

Esto NO significa que toda la aplicación deba ser pública.

Separar:

```text
PUBLIC DECA ENDPOINT
```

de:

```text
ADMIN APPLICATION
```

---

# 28. PRIVACIDAD

Los documentos pueden contener información empresarial y datos personales.

Debe aplicarse minimización de datos.

No exponer en logs:

- credenciales;
- tokens;
- información innecesaria;
- datos sensibles.

El repositorio administrativo debe estar protegido.

La URL pública únicamente debe proporcionar el documento correspondiente al DeCA.

No crear un índice público de documentos.

---

# 29. NO UTILIZAR LA URL PÚBLICA COMO API

La URL:

```text
/d/{token}
```

es un endpoint documental.

No debe devolver JSON ni una página HTML.

Debe devolver directamente el PDF correspondiente.

La API administrativa debe estar separada.

---

# 30. GENERACIÓN PDF

El PDF debe ser:

- nativo;
- legible;
- profesional;
- accesible visualmente;
- ≤5 MB;
- reproducible a partir de los datos estructurados;
- con QR;
- con fecha/hora;
- con identificador DeCA.

No generar el PDF mediante captura de pantalla.

No generar una imagen y convertirla a PDF.

---

# 31. DISEÑO DEL DOCUMENTO

El diseño debe priorizar:

1. Legibilidad.
2. Identificación rápida.
3. Datos obligatorios claramente diferenciados.
4. QR claramente visible.
5. Información del cargador.
6. Información del transportista.
7. Información del vehículo.
8. Origen/destino.
9. Mercancía/peso.
10. Fecha.

No es necesario copiar visualmente un modelo ministerial concreto si la normativa permite libre edición/formato, pero sí deben estar presentes todos los datos exigidos.

---

# 32. CARTAS DE PORTE COMO FUENTE

La normativa admite utilizar formatos de otros documentos de transporte como DeCA si contienen todos los datos exigidos.

Por tanto, en una fase posterior podría estudiarse si la propia carta de porte de Hispatec puede utilizarse como DeCA cuando se complete con los datos necesarios y el QR/URL correspondientes.

NO asumir automáticamente que nuestra carta de porte actual cumple todos los requisitos.

Debe existir una validación específica.

---

# 33. ARQUITECTURA RECOMENDADA

No fijar todavía una tecnología de infraestructura sin comparar alternativas.

La aplicación debe separar:

```text
DOMAIN
APPLICATION
INFRASTRUCTURE
UI
```

Conceptualmente:

```text
/src
   /domain
   /application
   /infrastructure
   /presentation
```

El dominio no debe depender directamente de:

- Google Apps Script;
- Supabase;
- Firebase;
- Cloud Run;
- Gmail;
- Microsoft 365.

Las integraciones deben implementarse mediante adapters/interfaces.

---

# 34. PORTABILIDAD

La aplicación debe poder cambiar de infraestructura sin reescribir el dominio.

Ejemplo:

```text
StorageService
    |
    +-- GoogleCloudStorage
    +-- SupabaseStorage
    +-- OtherStorage
```

Lo mismo para:

```text
EmailService
DocumentImporter
AuthService
```

---

# 35. TECNOLOGÍA

Antigravity debe proponer la arquitectura tecnológica más adecuada.

Debe comparar al menos:

- Google Apps Script.
- Google Cloud Run.
- Firebase.
- Supabase.
- otra alternativa si considera que aporta una ventaja clara.

Criterios:

- seguridad;
- coste;
- mantenimiento;
- facilidad de despliegue;
- rendimiento;
- generación PDF;
- almacenamiento;
- URLs públicas;
- correo;
- auditoría;
- escalabilidad;
- integración futura con Hispatec;
- facilidad de desarrollo.

No seleccionar tecnología únicamente por familiaridad.

---

# 36. MVP

El MVP debe limitarse a lo necesario.

## MVP-1

### Entrada

PDF carta de porte / CMR.

### Procesamiento

Extracción determinista.

### Maestros

Transportistas.

### Usuario

Introducción de matrícula.

### Validación

Datos obligatorios.

### Salida

DeCA PDF.

### QR

QR funcional.

### URL

URL HTTPS única.

### Storage

Almacenamiento persistente.

### Email

Envío del DeCA.

### Auditoría

Registro básico de operaciones.

---

# 37. NO HACER EN MVP

No introducir inicialmente:

- IA compleja;
- OCR avanzado si no es necesario;
- integración API Hispatec;
- aplicación móvil nativa;
- multiempresa;
- analítica avanzada;
- dashboard complejo;
- facturación;
- ERP;
- WMS;
- BI;
- automatizaciones innecesarias.

Primero demostrar el flujo completo real.

---

# 38. FUTURO

Posibles fases posteriores:

```text
FASE 2
CSV / Excel

FASE 3
Automatización de email

FASE 4
Integración Hispatec

FASE 5
OCR / documentos desconocidos

FASE 6
Automatización de órdenes de carga

FASE 7
Procesamiento masivo

FASE 8
Alertas y monitorización
```

---

# 39. PRINCIPIO DE DESARROLLO

Cada fase debe cumplir:

```text
DISEÑAR
   ↓
IMPLEMENTAR
   ↓
TESTEAR
   ↓
DOCUMENTAR
   ↓
VALIDAR
   ↓
SIGUIENTE FASE
```

No avanzar acumulando funcionalidades sin probar las anteriores.

---

# 40. TESTING

Debe existir testing automatizado.

Casos mínimos:

### Importación

- PDF válido.
- PDF vacío.
- PDF corrupto.
- PDF no reconocido.
- PDF duplicado.
- PDF > límite.

### Extracción

- campos completos;
- campos ausentes;
- formatos numéricos;
- nombres de transportistas diferentes.

### Matrícula

- matrícula válida;
- matrícula vacía;
- matrícula mal formada;
- tractor + remolque.

### Validación

- todos los campos;
- falta un campo;
- faltan varios campos.

### DeCA

- generación correcta;
- PDF nativo;
- tamaño ≤5 MB;
- QR;
- URL;
- metadatos.

### Versionado

- modificación;
- nueva versión;
- trazabilidad.

### Email

- envío correcto;
- error;
- reintento;
- evitar duplicados.

### Seguridad

- acceso no autorizado;
- manipulación de identificadores;
- acceso a otro DeCA;
- archivos maliciosos;
- inyección.

---

# 41. DEFINITION OF DONE

Una funcionalidad NO se considera terminada hasta que:

- está implementada;
- está testeada;
- está documentada;
- tiene manejo de errores;
- tiene validación;
- no introduce deuda técnica conocida innecesaria;
- cumple los requisitos de seguridad aplicables;
- cumple los requisitos legales aplicables;
- puede ejecutarse reproduciblemente.

---

# 42. DEUDA TÉCNICA

Antigravity debe señalar explícitamente cualquier deuda técnica.

No ocultarla.

Utilizar:

```text
TECH-DEBT
```

en documentación y código cuando sea necesario.

Cada deuda debe incluir:

- descripción;
- motivo;
- impacto;
- prioridad;
- solución futura.

---

# 43. REGLA CONTRA EL SOBRE-DISEÑO

DECA Light debe ser ligero.

No convertirlo en un ERP.

No crear abstracciones innecesarias.

No introducir microservicios si una arquitectura monolítica/modular es suficiente.

No añadir dependencias sin justificación.

No añadir IA porque "queda bien".

No añadir funcionalidades que no resuelvan un problema real.

---

# 44. REGLA CONTRA EL SUB-DISEÑO

Tampoco crear un script desechable.

La aplicación debe estar preparada para:

- crecimiento;
- auditoría;
- cambio de infraestructura;
- integración con Hispatec;
- múltiples transportistas;
- procesamiento de documentos;
- mantenimiento durante años.

---

# 45. OBSERVACIÓN LEGAL IMPORTANTE

El sistema es una herramienta informática.

La aplicación no debe pretender determinar automáticamente responsabilidades jurídicas que dependan de circunstancias del transporte.

Debe limitarse a:

- recopilar;
- validar;
- transformar;
- generar;
- almacenar;
- enviar;
- registrar.

Cuando exista una cuestión jurídica dudosa:

```text
LEGAL_REVIEW_REQUIRED
```

---

# 46. FUENTES NORMATIVAS PRINCIPALES

## Resolución de 5 de junio de 2026

BOE-A-2026-12784

https://www.boe.es/buscar/act.php?id=BOE-A-2026-12784

Esta resolución es la referencia técnica principal para DECA Light.

Aspectos especialmente relevantes:

- características de las aplicaciones;
- datos mínimos;
- creación antes del inicio efectivo;
- fecha/hora;
- repositorio;
- URL;
- PDF;
- QR;
- conservación;
- modificaciones;
- copia para conductor;
- utilización de otros formatos de transporte.

## Orden FOM/2861/2012

Debe utilizarse para determinar los datos sustantivos del documento de control de mercancías.

NO duplicar requisitos legales en código sin documentar su fuente.

---

# 47. REGLA DE ACTUALIZACIÓN NORMATIVA

La normativa puede cambiar.

El sistema debe tener documentada la versión normativa contra la que fue validado.

Ejemplo:

```text
LEGAL_SPEC_VERSION = 2026-10
```

Si aparece una modificación normativa:

1. revisar;
2. actualizar requisitos;
3. actualizar tests;
4. actualizar generación;
5. documentar el cambio.

---

# 48. INFORMACIÓN QUE TODAVÍA DEBE CONFIRMARSE

Antigravity NO debe inventar estos datos.

Deben quedar como configuración:

- razón social exacta;
- NIF;
- domicilio;
- email remitente;
- proveedor de correo;
- dominio definitivo;
- infraestructura definitiva;
- formatos exactos de las cartas de porte;
- campos exactos disponibles en Hispatec;
- datos reales de transportistas;
- política interna de conservación;
- usuarios autorizados.

Utilizar placeholders cuando todavía no estén definidos.

---

# 49. PRIORIDAD ABSOLUTA

El proyecto debe optimizar:

## 1. Tiempo de desarrollo

Llegar rápidamente a un flujo real funcionando.

## 2. Seguridad

No sacrificar seguridad para ganar velocidad.

## 3. Cumplimiento

No generar documentos que incumplan requisitos conocidos.

## 4. Agilidad operativa

Reducir al mínimo el trabajo manual.

## 5. Mantenibilidad

No crear un sistema imposible de mantener.

---

# 50. FLUJO OBJETIVO FINAL

El éxito de DECA Light se resume en:

```text
EXPORTAR CARTAS DE PORTE
            ↓
IMPORTAR
            ↓
RECONOCER
            ↓
ASIGNAR MATRÍCULA
            ↓
VALIDAR
            ↓
GENERAR DECA
            ↓
QR + URL
            ↓
ALMACENAR
            ↓
ENVIAR
            ↓
REGISTRAR
```

El usuario no debe tener que pensar en la complejidad interna.

La complejidad debe estar en el software.

---

# 51. PRIMER OBJETIVO DE ANTIGRAVITY

NO empezar programando inmediatamente.

Primero debe:

1. Leer este MASTER_CONTEXT.
2. Identificar requisitos funcionales.
3. Identificar requisitos no funcionales.
4. Identificar incertidumbres.
5. Identificar riesgos.
6. Proponer arquitectura.
7. Comparar infraestructura.
8. Proponer modelo de datos.
9. Proponer estructura de proyecto.
10. Proponer roadmap MVP.
11. Proponer estrategia de testing.
12. Señalar cualquier contradicción o requisito que necesite confirmación.

Después de esto se revisará la propuesta y se autorizará la implementación.

---

# 52. REGLA FINAL PARA ANTIGRAVITY

No asumir.

No inventar.

No ocultar incertidumbres.

No implementar requisitos legales basándose únicamente en memoria del modelo.

Cuando un requisito normativo sea relevante:

**identificar la fuente y documentarla.**

Cuando una decisión técnica sea reversible:

**mantenerla desacoplada.**

Cuando una funcionalidad no sea necesaria para el MVP:

**posponerla.**

Cuando una funcionalidad sea necesaria para seguridad, trazabilidad o cumplimiento:

**no posponerla.**

El objetivo es construir rápidamente una aplicación pequeña, profesional y mantenible que resuelva un problema real de la operativa diaria de Tomates de Autor.

# DESIGN SYSTEM / UI

DECA Light debe utilizar como referencia visual principal el lenguaje de diseño
ya utilizado en CCO y en la aplicación logística de la empresa.

DECA Light debe sentirse como una aplicación perteneciente al mismo ecosistema.

Como referencias externas de producto SaaS moderno se utilizarán:

- Stripe
- Linear
- Ramp
- Mercury

Estas referencias se utilizarán únicamente como inspiración para:

- jerarquía visual;
- navegación;
- densidad de información;
- tablas;
- formularios;
- estados;
- feedback;
- acciones;
- componentes;
- consistencia;
- experiencia de usuario.

NO copiar literalmente interfaces, branding, logotipos, assets ni diseños propietarios.

Prioridades:

1. Velocidad operativa.
2. Claridad.
3. Accesibilidad.
4. Consistencia con CCO/App Logística.
5. Estética SaaS moderna.

Antes de crear componentes nuevos, revisar si existe un patrón equivalente
en CCO/App Logística que pueda reutilizarse conceptualmente.

La interfaz debe evitar complejidad visual innecesaria.

El usuario debe poder identificar rápidamente:

- documentos importados;
- expediciones pendientes;
- matrículas pendientes;
- errores;
- DECAs preparados;
- DECAs enviados;
- acciones disponibles.

La interfaz debe estar diseñada para procesamiento rápido de múltiples
expediciones.


---

# 53. PROTOCOLO DE CONTINUIDAD, GOBERNANZA Y FLUJO DE TRABAJO MULTI-AGENTE (CHATGPT, GEMINI, ANTIGRAVITY)

Para garantizar la estabilidad a largo plazo del proyecto y evitar regresiones, inconsistencias o asunciones infundadas durante el desarrollo asistido por múltiples modelos de Inteligencia Artificial (ChatGPT, Gemini, Antigravity), se establecen los siguientes roles, responsabilidades y reglas operativas estrictas:

## 53.1 Roles y Distribución de Responsabilidades
1. **ChatGPT (Diseño Funcional, Dominio y Estrategia de Producto):**
   - Responsable de definir los requerimientos de negocio, el modelo conceptual de dominio, las reglas operativas hortofrutícolas y el análisis regulatorio (FOM/2861/2012, BOE-A-2026-12784).
   - Genera especificaciones funcionales, user stories, casos de uso y criterios de aceptación.
   - No ejecuta cambios directos sobre el workspace ni asume el estado del filesystem sin verificación.

2. **Gemini / Modelos de Auditoría (Revisión Crítica, Arquitectura y Verificación):**
   - Responsable de realizar análisis estático, revisiones de arquitectura hexagonal, auditorías de seguridad (anti-IDOR, criptografía de tokens, inmutabilidad legal) y detección de contradicciones documentales.
   - Diseña estrategias de migración, planes de contingencia y checklists de verificación antes de cada cambio estructural.

3. **Antigravity (Ingeniero Principal Ejecutor en Workspace Local):**
   - Agente pair-programming conectado directamente al entorno local (Windows PowerShell, Python `.venv`, Git).
   - Ejecuta inspección real de archivos, pruebas automatizadas (`pytest`), generación de código, migraciones (`alembic`) y operaciones Git controladas.
   - Actúa como salvaguarda del workspace: prohíbe operaciones destructivas no autorizadas (`git reset --hard`, `git clean`, `git push` sin autorización expresa).

## 53.2 Protocolo de Handoff y Fuente de Verdad
- **Fuente de Verdad Técnica:** La única fuente de verdad sobre el estado del código es el repositorio Git local (`master`), el filesystem real y la suite de pruebas automatizadas.
- **Documentos de Continuidad:**
  - `MASTER_CONTEXT.md`: Especificación técnica global, reglas de negocio y gobernanza del proyecto.
  - `PROJECT_STATE.md`: Cuaderno de bitácora vivo que refleja la fase activa, el último commit, los cambios aplicados, su nivel de verificación empírica y el siguiente paso recomendado.
- **Regla de No Asunción:** Ningún agente puede afirmar que una funcionalidad existe o que un test pasa basándose en el historial de chat anterior; todo estado debe ser verificado con herramientas en tiempo real (`git status`, `pytest`, `Test-Path`). Cualquier afirmación no verificada directamente debe marcarse explícitamente como `[PENDIENTE DE VERIFICACIÓN]`.
- **Commits y Sincronización:**
  - Commits atómicos y convencionales (`feat:`, `fix:`, `chore:`, `refactor:`, `test:`).
  - Cada fase debe concluir con la suite completa de pruebas ejecutándose con éxito (cero errores).
  - Prohibido hacer `git push` a `origin` sin que el usuario emita la orden exacta y expresa: `"AUTORIZO PUSH"`.

---

# 54. DECISIONES INNEGOCIABLES Y PRINCIPIOS DE INGENIERÍA

Las siguientes directrices son de cumplimiento obligatorio y no pueden ser alteradas sin un Architecture Decision Record (ADR) formalmente aprobado:

1. **Aislamiento Absoluto del Dominio (Clean Architecture / Hexagonal):**
   - El núcleo de negocio (`src/domain/`) no tiene dependencias externas: prohíbe importar SQLAlchemy, FastAPI, Pydantic, ReportLab, Segno o cualquier biblioteca de infraestructura.
   - Las reglas de validación legal (FOM/2861/2012) residen exclusivamente en entidades y value objects del dominio.

2. **Inmutabilidad Documental y Custodia Legal (1 Año):**
   - Conforme a la Orden FOM/2861/2012, una vez que un DeCA es generado y emitido, el documento y sus versiones son jurídicamente inmutables durante al menos 1 año.
   - En la base de datos relacional, queda terminantemente prohibido el borrado en cascada (`ON DELETE CASCADE`) que pueda destruir versiones (`deca_versions`) o registros de auditoría de entrega (`email_deliveries`). Se debe aplicar política de restricción (`ON DELETE RESTRICT`) o borrado lógico auditado.

3. **Token Público Criptográfico Separado del Identificador Interno:**
   - Para la inspección pública en carretera por las autoridades (Guardia Civil / Inspectores de Transporte), se genera una URL con token de 256 bits (`secrets.token_urlsafe(32)`).
   - Se prohíbe exponer claves primarias internas (UUIDs o autoincrementales) en URLs públicas o códigos QR para prevenir ataques de enumeración (anti-IDOR) y scraping de datos operativos.

4. **Extracción Determinista de Albaranes sin Dependencia de IA:**
   - La ingesta de albaranes de Hispatec ERP se realiza mediante parsers deterministas basados en capas de texto nativo (`pdfplumber` / `pypdf`) y expresiones regulares.
   - No se emplean LLMs en el pipeline nuclear de extracción para evitar alucinaciones en campos críticos (NIFs, matrículas, kilos, fechas).

5. **Aislamiento Multiempresa Estricto (Tenant Isolation):**
   - Aunque Tomates de Autor S.L. y empresas vinculadas (ej. Cultivos Araba) compartan infraestructura y catálogo de transportistas/vehículos, los datos operativos (`expediciones`, `decas`, `configuraciones`, `entregas`) deben estar estrictamente particionados mediante `company_id`.
   - Los números de albarán (`reference`) pueden duplicarse entre empresas distintas; la identidad unívoca de expedición la proporciona el identificador interno secuencial `internal_id` (`TD-YYYY-NNNNN`) y la clave compuesta `(company_id, reference)`.

6. **Coexistencia Segura durante la Transición de Persistencia:**
   - Los repositorios en memoria (`InMemory*`) existentes no deben eliminarse ni desconectarse hasta que los adaptadores SQLAlchemy (`SqlAlchemy*Repository`) estén 100% implementados, probados con la suite de integración y validados mediante tests de aceptación antes de conmutar las dependencias de FastAPI.

---

# 55. ARQUITECTURA TÉCNICA CONSOLIDADA Y MAPA DE INFRAESTRUCTURA

## 55.1 Stack Tecnológico
- **Lenguaje:** Python 3.12+ (tipado estricto con `typing`, `pydantic v2` en capa de aplicación/presentación).
- **Framework Web / API:** FastAPI + Starlette (Uvicorn como servidor ASGI).
- **ORM y Migraciones:** SQLAlchemy 2.0 (modo declarativo moderno 2.0) + Alembic.
- **Motor de Base de Datos:**
  - Desarrollo local y tests rápidos: SQLite en modo WAL (`sqlite+pysqlite:///deca_light.db`).
  - Entorno de producción / staging: PostgreSQL 16+ en contenedor Docker.
- **Generación Documental:** ReportLab (diseño vectorial tabular ultraligero y canónico de 1 página A4).
- **Códigos QR:** Segno (generador QR vectorial puro sin dependencias complejas de C).
- **Ingesta de Documentos:** `pdfplumber` / `pypdf` para extracción geométrica determinista.
- **Testing:** `pytest` con plugins de integración (`pytest-asyncio`, `httpx`).

## 55.2 Mapa de Capas y Dependencias
```
[ PRESENTACIÓN ]    --> FastAPI Routers, Schemas Pydantic, Middleware, Templates CCO
        │
        ▼
[ APLICACIÓN ]      --> Casos de Uso (Import, AssignVehicle, GenerateDeCA, DeliverEmail)
        │               DTOs, Interfaces de Puertos (Repositories, Storages, Notifiers)
        ▼
[  DOMINIO  ]       --> Entidades (Expedicion, DeCA, Transportista, Vehiculo)
                        Value Objects (NIF, Matricula, DeCAToken, SnapshotHash)
                        Servicios de Dominio & Reglas FOM/2861/2012
        ▲
        │
[ INFRAESTRUCTURA ] --> Adaptadores SQLAlchemy (PostgreSQL/SQLite)
                        Adaptador ReportLab (PdfRenderer)
                        Adaptador Segno (QrGenerator)
                        Adaptadores Storage (LocalFileSystem, S3)
                        Adaptadores Notificación (Microsoft Graph API v1.0, SMTP)
```

---

# 56. ESTRATEGIA DE AUTOMATIZACIÓN, INTELIGENCIA ARTIFICIAL Y AGENTES

## 56.1 Principio rector
DECA Light debe priorizar una automatización determinista, fiable y auditable. La inteligencia artificial se incorporará únicamente cuando aporte valor demostrado en tareas de interpretación, clasificación o asistencia.

La IA no debe sustituir las reglas de negocio ni convertirse en la fuente de verdad de la aplicación.

## 56.2 Automatización determinista
Las siguientes operaciones deben permanecer bajo control de la lógica convencional de la aplicación:
- Identificación y persistencia de expediciones.
- Conservación exacta del número de albarán.
- Detección de duplicados.
- Emparejamiento de matrículas por número de albarán, nunca por posición de fila.
- Validación de datos obligatorios.
- Control de estados y transiciones.
- Generación de documentos a partir de datos validados.
- Versionado, auditoría y conservación documental.
- Gestión de permisos, sesiones y transacciones.
- Registro y control de los envíos.

## 56.3 Uso futuro de IA especializada
Se podrán estudiar modelos de IA para:
- Interpretar documentos con estructuras inesperadas.
- Proponer campos que no hayan podido extraerse mediante reglas convencionales.
- Identificar discrepancias entre los documentos originales y los datos extraídos.
- Clasificar incidencias y explicar por qué una expedición está bloqueada.
- Proponer correcciones para su revisión.
- Resumir incidencias y detectar patrones operativos.

La extracción determinista de texto y los parsers existentes serán la primera opción cuando resulten suficientes. El OCR se reservará para documentos escaneados sin texto utilizable.

La IA debe distinguir entre datos confirmados, datos propuestos y datos pendientes de verificación. No puede inventar datos ni presentar inferencias como hechos confirmados.

## 56.4 Agentes de IA
En una fase posterior podrá evaluarse un asistente operativo con herramientas y permisos limitados.

Podrá consultar expediciones, resumir pendientes, analizar incidencias y preparar propuestas o borradores.

No podrá saltarse las validaciones, confirmar automáticamente datos dudosos, emitir documentos incompletos, borrar registros históricos ni ejecutar operaciones sensibles sin los controles establecidos.

No se deben crear múltiples agentes independientes hasta que exista una necesidad real que justifique esa complejidad.

## 56.5 n8n e integraciones externas
n8n es una posibilidad futura para orquestar correos, notificaciones, tareas programadas y otros sistemas.

No sustituirá a FastAPI como núcleo de negocio ni a PostgreSQL como fuente de verdad.

No se debe introducir n8n, proveedores de IA, colas de trabajo o nuevas infraestructuras hasta justificar su necesidad.

## 56.6 Correo corporativo
Se prevé el envío de DeCA desde una cuenta corporativa autorizada.

La implementación deberá estudiar primero el proveedor real de correo de la empresa y el método de integración adecuado.

Se contemplarán los destinatarios asociados a transportistas, envíos individuales o agrupados, revisión previa, trazabilidad, gestión de errores, reintentos e idempotencia.

La aceptación de un envío por el proveedor no debe confundirse con la entrega o recepción efectiva del mensaje.

Esta funcionalidad sigue pendiente y no debe documentarse como implementada.

## 56.7 Seguridad y control humano
La IA debe trabajar con permisos mínimos y herramientas expresamente autorizadas.

Las operaciones con consecuencias documentales o legales deben estar protegidas mediante validaciones deterministas, auditoría y aprobación humana cuando corresponda.

La utilización de IA no constituye por sí misma una garantía de cumplimiento normativo.

## 56.8 Orden de evolución estratégica
Se documenta la siguiente secuencia estratégica:
1. Persistencia y adaptadores SQLAlchemy.
2. Validación de la importación de cartas de porte y CMR.
3. Expediciones pendientes agrupadas por transportista.
4. Incorporación y emparejamiento de matrículas.
5. Validación y generación de DeCA.
6. Almacenamiento persistente, enlaces y QR.
7. Integración con el correo corporativo.
8. Evaluación de IA para las excepciones reales observadas.
9. Evaluación de agentes y n8n cuando aporten valor demostrado.

Esta secuencia es una hoja de ruta orientativa. No autoriza a implementar todas las fases ni modifica la prioridad técnica inmediata.

## 56.9 Reglas de gobernanza de ingeniería
Las siguientes reglas complementan las directrices de continuidad del proyecto:
- Inspeccionar el código real antes de proponer cambios.
- Separar diagnóstico, propuesta, implementación y validación.
- Dividir las tareas complejas en subfases pequeñas.
- No inventar clases, interfaces, estados ni funcionalidades.
- Mantener las pruebas existentes y añadir pruebas específicas.
- No ejecutar migraciones sobre bases de datos persistentes sin autorización expresa.
- No hacer commits ni pushes sin autorización expresa.
- No utilizar credenciales reales ni conectar servicios externos sin autorización.
- Actualizar la documentación de continuidad al finalizar cada fase autorizada.
- Distinguir lo implementado, lo probado y lo que solo está previsto.