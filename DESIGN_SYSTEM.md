# DECA LIGHT — DESIGN SYSTEM Y DIRECTRICES VISUALES

**Proyecto:** DECA Light  
**Empresa:** Tomates de Autor S.L.  
**Versión:** 1.0  
**Fecha:** 12/10/2026  
**Estado:** Especificación de Diseño y Directrices Visuales Aprobadas  
**Tecnología Base de Presentación:** FastAPI + Jinja2 + HTMX + CSS Semántico (Server-Side Rendering Ligero)

---

## 1. FILOSOFÍA VISUAL Y PRINCIPIOS DE DISEÑO

DECA Light es una herramienta de misión crítica para la operativa diaria de almacén y expediciones de **Tomates de Autor S.L.** y sociedades del grupo (ej. Cultivos Araba). Su interfaz de usuario debe alinearse conceptual y estéticamente con el Centro de Control de Operaciones (CCO) y las aplicaciones logísticas internas de la empresa.

### 1.1 Principios Fundamentales
1. **Velocidad Operativa y Orientación a Tareas:**
   - Diseñado para personal administrativo y de muelle que procesa decenas de expediciones al día.
   - Cada clic, recarga de página o milisegundo de latencia innecesario representa fricción en la expedición de camiones.
   - Ausencia total de dashboards ornamentales, gráficos decorativos o widgets superfluos. La pantalla principal es una **bandeja de trabajo activa**.
2. **Claridad sobre Decoración:**
   - La jerarquía visual debe responder de inmediato a tres preguntas del operador:
     - *¿Qué documentos se han importado?*
     - *¿Qué expediciones están bloqueadas esperando matrícula?*
     - *¿Qué DeCAs están listos para emitirse o enviarse?*
3. **Referencias Conceptuales de Producto SaaS:**
   - **Linear:** Para la jerarquía visual sobria, tipografía técnica, navegación compacta y soporte nativo para atajos de teclado.
   - **Stripe:** Para la alta densidad de las tablas de datos, filtros combinados, visualización de estados documentales y paneles laterales de detalle (*drawers* / *sheets*).
   - **Shippo:** Para la claridad en los flujos logísticos de expedición, asignación de tracción y carga, y confirmación de emisiones.
   - *Regla estricta de marca:* Estas referencias se utilizan exclusivamente como inspiración ergonómica y funcional. Queda terminantemente prohibido copiar marcas, logos, estilos propietarios o componentes registrados.

---

## 2. IDENTIDAD VISUAL Y DESIGN TOKENS

### 2.1 Enfoque de Color y Modos
- **Modo Claro (Por Defecto e Inicial):** Diseñado específicamente para entornos de oficina de báscula, oficinas de muelle y almacén con iluminación diurna o fluorescente intensa. Ofrece máximo contraste y legibilidad.
- **Modo Oscuro (Extensión Futura):** No es un requisito del MVP, pero todos los colores se definen mediante tokens CSS desacoplados para permitir su implementación futura sin refactorizar HTML.
- **Estructura y Marca:** Azul marino profundo (`#0F172A` / `#1E293B`) para la barra superior, navegación y elementos de cabecera institucional.
- **Paleta Neutra:** Escala Slate/Zinc (`#F8FAFC`, `#F1F5F9`, `#E2E8F0`, `#64748B`, `#0F172A`) para fondos, bordes de tabla y jerarquía de textos.

### 2.2 Variables CSS Semánticas (Design Tokens)

```css
:root {
  /* -------------------------------------------------------------------------
     Paleta Base Neutra
     ------------------------------------------------------------------------- */
  --color-bg-app: #F8FAFC;          /* slate-50: fondo general de la aplicación */
  --color-bg-surface: #FFFFFF;      /* blanco: tarjetas, tablas, modales */
  --color-bg-subtle: #F1F5F9;       /* slate-100: cabeceras de tabla, fondos secundarios */
  --color-bg-muted: #E2E8F0;        /* slate-200: separadores, fondos inactivos */

  /* -------------------------------------------------------------------------
     Bordes y Líneas de División
     ------------------------------------------------------------------------- */
  --color-border-subtle: #E2E8F0;   /* slate-200: bordes de celda y divisores */
  --color-border-strong: #CBD5E1;   /* slate-300: bordes de input y contenedores */
  --color-border-focus: #2563EB;    /* blue-600: anillo de foco interactivo */

  /* -------------------------------------------------------------------------
     Tipografía y Textos
     ------------------------------------------------------------------------- */
  --color-text-primary: #0F172A;     /* slate-900: texto principal y títulos */
  --color-text-secondary: #475569;   /* slate-600: texto explicativo y metadatos */
  --color-text-muted: #94A3B8;       /* slate-400: placeholders y marcas de agua */
  --color-text-inverse: #FFFFFF;     /* blanco: texto sobre fondos oscuros */

  /* -------------------------------------------------------------------------
     Estructura de Marca (Tomates de Autor / CCO)
     ------------------------------------------------------------------------- */
  --color-brand-marine: #0F172A;     /* azul marino profundo estructural */
  --color-brand-marine-light: #1E293B;
  --color-brand-accent: #2563EB;     /* azul corporativo de acción */
  --color-brand-accent-hover: #1D4ED8;

  /* -------------------------------------------------------------------------
     Colores Semánticos de Estado (Multi-nivel)
     ------------------------------------------------------------------------- */
  /* Estado: Éxito / Emitido / Validado (Verde Esmeralda) */
  --color-status-success-bg: #ECFDF5;
  --color-status-success-text: #065F46;
  --color-status-success-border: #A7F3D0;
  --color-status-success-dot: #10B981;

  /* Estado: Advertencia / Pendiente Matrícula / Revisión (Ámbar Cálido) */
  --color-status-warning-bg: #FFFBEB;
  --color-status-warning-text: #92400E;
  --color-status-warning-border: #FDE68A;
  --color-status-warning-dot: #F59E0B;

  /* Estado: Error / Incompleto / Revocado (Rojo Carmesí) */
  --color-status-error-bg: #FEF2F2;
  --color-status-error-text: #991B1B;
  --color-status-error-border: #FECACA;
  --color-status-error-dot: #EF4444;

  /* Estado: Neutro / Importada / En Espera (Slate) */
  --color-status-neutral-bg: #F1F5F9;
  --color-status-neutral-text: #334155;
  --color-status-neutral-border: #CBD5E1;
  --color-status-neutral-dot: #64748B;

  /* Estado: Informativo / Lista para DeCA (Azul Cobalto) */
  --color-status-info-bg: #EFF6FF;
  --color-status-info-text: #1E40AF;
  --color-status-info-border: #BFDBFE;
  --color-status-info-dot: #3B82F6;

  /* -------------------------------------------------------------------------
     Espaciado y Radios de Borde
     ------------------------------------------------------------------------- */
  --radius-sm: 3px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-pill: 9999px;

  /* Sombras Técnicas y Planas */
  --shadow-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --shadow-drawer: -4px 0 24px rgba(0, 0, 0, 0.15);
}
```

---

## 3. TIPOGRAFÍA, ESPACIADO Y COMPONENTES REUTILIZABLES

### 3.1 Pila Tipográfica y Jerarquía
- **Texto General (`font-sans`):** `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`.
  - Excelente legibilidad en cuerpos pequeños (12px - 14px), distinción clara entre caracteres y rendimiento nativo sin carga pesada.
- **Códigos y Datos Técnicos (`font-mono`):** `"JetBrains Mono", Consolas, "Liberation Mono", Menlo, monospace`.
  - **Obligatoria** para: matrículas de tractor y remolque, identificador interno `internal_id` (`TD-YYYY-NNNNN`), números de albarán/CMR, códigos DeCA (`DECA-YYYY-NNNNNN`), NIFs/CIFs y hashes criptográficos SHA-256.

| Nivel | Tamaño | Peso | Altura de Línea | Uso Principal |
| :--- | :--- | :--- | :--- | :--- |
| `Heading 1` | 20px (`1.25rem`) | 600 (Semibold) | 28px | Título principal de la bandeja / Vista activa |
| `Heading 2` | 16px (`1.00rem`) | 600 (Semibold) | 24px | Cabeceras de paneles laterales y modales |
| `Heading 3` | 13px (`0.81rem`) | 600 (Semibold) | 18px | Cabeceras de sección en formularios y drawers |
| `Body Base` | 13px (`0.81rem`) | 400 (Regular) | 18px | Celdas de tabla, valores de formulario |
| `Body Small` | 12px (`0.75rem`) | 400 (Regular) | 16px | Etiquetas de ayuda, timestamps, metadatos secundarios |
| `Caption` | 11px (`0.69rem`) | 500 (Medium) | 14px | Status Badges, contadores de pestañas, etiquetas mono |

### 3.2 Escala de Espaciado Modular
Se utiliza una escala estricta de múltiplos de 4px para garantizar alineaciones impecables:
- `4px` (`space-1`): Separación entre icono y texto en botones, espaciado interno de badges.
- `8px` (`space-2`): Padding vertical en celdas de tabla densa, espaciado entre inputs relacionados.
- `12px` (`space-3`): Padding horizontal de botones e inputs, separación de items en barras de herramientas.
- `16px` (`space-4`): Padding estándar de tarjetas y contenedores de formulario.
- `24px` (`space-6`): Separación entre bloques estructurales.
- `32px` (`space-8`): Márgenes generales de página y vistas principales.

### 3.3 Catálogo de Componentes Base

#### A. Botones (`.btn`)
- **Primario (`.btn-primary`):** Fondo `--color-brand-marine`, texto blanco. Para la acción principal (ej. *"Generar DeCA"*, *"Confirmar Asignación"*).
- **Secundario (`.btn-secondary`):** Fondo blanco, borde `--color-border-strong`, texto `--color-text-primary`. Para acciones auxiliares (ej. *"Cancelar"*, *"Exportar CSV"*).
- **Acción Destacada (`.btn-accent`):** Fondo `--color-brand-accent` (`#2563EB`), texto blanco. Para flujos de importación o emisión masiva.
- **Destructivo (`.btn-destructive`):** Fondo blanco, borde `--color-status-error-border`, texto `--color-status-error-text`. Para revocaciones o cancelaciones.
- **Fantasma / Icono (`.btn-ghost`):** Sin borde ni fondo por defecto; hover sutil. Para atajos, copiar código o cerrar paneles.
- **Estado de Carga (`.btn.is-loading`):** Spinner SVG discreto incrustado; botón deshabilitado para prevenir doble clic transaccional.

#### B. Etiquetas de Estado (`.badge-status`)
Las etiquetas de estado siempre combinan **color de fondo suave**, **texto de alto contraste**, **borde perimetral** y un **punto indicador circular** (`dot`), garantizando plena accesibilidad sin depender exclusivamente del color:

```html
<!-- Ejemplo: Expedición Pendiente de Matrícula -->
<span class="badge-status badge-warning" role="status">
  <span class="badge-dot" aria-hidden="true"></span>
  <span>PENDIENTE MATRÍCULA</span>
</span>
```

#### C. Tablas de Alta Densidad (`.data-table`)
- Cabecera fija (`position: sticky; top: 0`) con fondo `--color-bg-subtle` y borde inferior marcado.
- Celdas compactas (padding: `8px 12px`).
- Fila con hover sutil (`--color-bg-subtle`) y cursor interactivo para seleccionar la expedición.
- Alineación estricta:
  - Textos descriptivos (destinos, cargador): Alineados a la izquierda.
  - Códigos, fechas y matrículas: Alineados al centro con tipografía monoespaciada.
  - Kilos, bultos y cantidades numéricas: Alineados a la derecha con fuentes tabulares (`font-variant-numeric: tabular-nums`).
- Casillas de verificación (`checkbox`) integradas en la primera columna para selección múltiple por lotes.

#### D. Panel Lateral de Detalle (*Detail Drawer / Sheet*)
- Al hacer clic en cualquier expedición de la tabla, se abre un panel lateral flotante (`width: 480px` a `560px`) desde la derecha con sombra `--shadow-drawer`.
- **Ventaja operativa:** La persona usuaria nunca pierde el scroll, la página ni la fila activa de la tabla mientras consulta los datos normativos completos o visualiza la previsualización del documento PDF original.
- Cierre rápido mediante tecla `Escape` o botón de cierre superior.

---

## 4. NAVEGACIÓN Y PANTALLAS PRINCIPALES

La arquitectura de la interfaz prioriza el flujo de trabajo de tráfico y báscula:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  [DECA LIGHT]  Tomates de Autor S.L. ▼      [ Buscar (Ctrl+K) ]      [ Importar PDFs ] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [Todas (48)]  [Pend. Matrícula (14)]  [Pend. Revisión (3)]  [Listas (18)]  [Emitidas] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Filtros: Fecha: Hoy ▼  | Transportista: Todos ▼  | [x] Solo con discrepancias          │
├────────────────────────────────────────────────────────────────┬───────────────────────┤
│ [ ] ID INTERNO   ALBARÁN     FECHA       TRANSPORTISTA   ESTADO│ DETALLE EXPEDICIÓN    │
│ ────────────────────────────────────────────────────────────── │ ───────────────────── │
│ [x] TD-2026-001  ALB-9981   12/10/2026   TRANSPORTES S.A [PEND]│ Matrícula: [ Asignar ]│
│ [ ] TD-2026-002  ALB-9982   12/10/2026   LOGÍSTICA DEL S [LIST]│ Cargador: TDA S.L.    │
│ [ ] TD-2026-003  CMR-4410   12/10/2026   HERMANOS GARCIA [EMIT]│ Destino: Perpignan    │
└────────────────────────────────────────────────────────────────┴───────────────────────┘
```

### 4.1 Pestañas de Filtrado Rápido (Bandejas de Trabajo)
1. **Todas:** Visión global del registro operativo de la jornada.
2. **Pendientes de Matrícula (Prioridad 1):**
   - Agrupa las expediciones importadas de Hispatec cuyo transporte ya está planificado pero falta introducir el camión definitivo en muelle.
   - Acceso inmediato con un solo clic o atajo de teclado (`1`).
3. **Pendientes de Validación / Revisión:**
   - Expediciones que presentan discrepancias normativas (ej. peso nulo, NIF transportista desconocido, formato de matrícula inválido).
4. **Listas para Emitir:**
   - Expediciones que cumplen el 100% de los requisitos legales de la Orden FOM/2861/2012 y están preparadas para la firma y generación del DeCA con su código QR.
5. **DeCAs Emitidos / Histórico:**
   - Documentos generados con token público activo (`/d/{token}`), código QR y trazabilidad de entrega por correo al transportista.

### 4.2 Barra de Filtros y Búsqueda Permanente
- Buscador rápido con atajo de teclado (`Ctrl + K` o `/`).
- Capacidad de filtrar instantáneamente por:
  - Matrícula de tractor o remolque (`1234BBB`, `R1234BBB`).
  - Número de albarán o referencia de Hispatec (`ALB-9981`).
  - Identificador correlativo interno (`TD-2026-00001`).
  - Razón social o NIF del transportista.
  - Código único del DeCA (`DECA-2026-000042`).

---

## 5. OPERATIVA LOGÍSTICA Y REGLAS DE DOMINIO

### 5.1 Importación Múltiple de Documentos
- Zona de arrastrar y soltar (*Dropzone*) prominente y accesible en cualquier momento.
- Admite selección masiva de múltiples archivos PDF simultáneamente.
- **Feedback de importación atómico:**
  - Muestra barra de progreso de ingesta con recuento en tiempo real.
  - Resumen post-procesamiento claro:
    - `18 albaranes procesados correctamente`.
    - `2 albaranes duplicados omitidos` (identificados por hash SHA-256).
    - `1 archivo con error de parseo` (con enlace directo para revisión manual).

### 5.2 Procesamiento y Acciones por Lotes (*Batch Operations*)
- Selección de expediciones mediante checkboxes individuales o botón "Seleccionar todas las visibles".
- Al seleccionar una o más filas, aparece una **barra de acciones por lotes** flotante en la parte inferior:
  - `[ Asignar Transportista / Matrícula a las 6 seleccionadas ]`
  - `[ Validar Requisitos Legales ]`
  - `[ Emitir DeCAs en Lote (6) ]`

### 5.3 Asignación Segura de Matrículas (Prevención de Errores Legales)
La interfaz debe evitar taxativamente que se generen DeCAs con vehículos mal tipificados (conforme al ADR-008 y las reglas de dominio):
- **Selector explícito de tipo de vehículo:**
  - `RIGIDO`:
    - Campo de matrícula de vehículo/tractor: **Obligatorio**.
    - Campo de semirremolque: **Deshabilitado visualmente y bloqueado** (muestra indicación *"No aplicable a camión rígido"*).
  - `ARTICULADO`:
    - Campo de matrícula de tractora: **Obligatorio**.
    - Campo de matrícula de semirremolque/plataforma: **Obligatorio** (validación visual de prefijo `R-` para remolques españoles).
- **Cruce con Maestro de Vehículos:**
  - Desplegable inteligente con autocompletado basado en los vehículos habituales del transportista asignado, reduciendo la entrada manual a un solo clic.

### 5.4 Mapeo Visual de los Estados Reales del Dominio

| Estado Dominio (`ExpeditionStatus`) | Etiqueta Visual | Clase CSS | Indicador Visual | Significado Operativo |
| :--- | :--- | :--- | :--- | :--- |
| `IMPORTADA` | Importada | `.badge-neutral` | Punto Gris Pizarra | Albarán cargado desde PDF; pendiente de asignación o revisión. |
| `PENDIENTE_MATRICULA` | Pendiente Matrícula | `.badge-warning` | Punto Ámbar Pulsante | Expedición en muelle a la espera del camión definitivo. |
| `PENDIENTE_REVISION` | Requiere Revisión | `.badge-error` | Punto Rojo | Discrepancia en pesos, NIFs o datos obligatorios de la carta de porte. |
| `LISTA_PARA_DECA` | Lista para Emitir | `.badge-info` | Punto Azul | Validada conforme a Orden FOM/2861/2012; lista para generar DeCA. |
| `DECA_GENERADO` | DeCA Generado | `.badge-success` | Punto Verde Esmeralda | PDF formal creado, QR vectorial sellado y custodia legal iniciada. |
| `ENVIADA` | DeCA Enviado | `.badge-success` | Icono Correo Verde | Correo electrónico entregado con éxito al transportista efectivo. |
| `ERROR` | Error de Emisión | `.badge-error` | Icono Alerta Rojo | Fallo en motor documental, correo o validación normativa. |
| `CANCELADA` / `REVOCADA` | Cancelada / Revocada | `.badge-neutral` | Tachado Gris | Expedición cancelada o DeCA revocado legalmente. |

---

## 6. DISEÑO RESPONSIVE Y ACCESIBILIDAD (A11Y)

### 6.1 Adaptación por Dispositivos y Contexto Operativo
1. **Escritorio de Oficina ($\ge 1280\text{px}$ — Entorno Principal):**
   - Diseñado para pantallas de tráfico y báscula (1080p / 1440p).
   - Layout de alta densidad: tabla completa de 8-10 columnas y panel lateral de detalle abierto simultáneamente.
   - Navegación optimizada para teclado (`Tab`, flechas, atajos de confirmación).
2. **Tablet en Muelle de Almacén ($768\text{px} - 1024\text{px}$):**
   - Utilizado por operarios en carretillas o pie de muelle con tablets táctiles.
   - Objetivos táctiles ampliados: botones con área interactiva mínima de **$44 \times 44\text{px}$**.
   - Tabla simplificada (oculta columnas secundarias como NIF o hashes, priorizando albarán, matrícula y estado).
3. **Móvil / Terminal de Mano ($< 768\text{px}$):**
   - Vista de contingencia para consulta rápida y verificación de expedición.
   - Las tablas se transforman en **tarjetas verticales apiladas**, con el botón de confirmación de matrícula destacado.

### 6.2 Criterios de Accesibilidad (WCAG 2.1 Nivel AA)
- **Contraste de Color:** Todos los textos principales cumplen una relación de contraste mínima de **$4.5:1$** sobre su fondo; los títulos y controles grandes superan **$3:1$**.
- **Foco Visible:** Todos los elementos interactivos (`button`, `input`, `select`, `a`) disponen de un anillo de foco inequívoco mediante `:focus-visible` (`outline: 2px solid var(--color-border-focus); outline-offset: 2px`).
- **Navegación Íntegra por Teclado:**
  - `Tab` / `Shift+Tab`: Recorrido ordenado de la interfaz.
  - `Enter` / `Espacio`: Activación de botones y selección de filas.
  - `Escape`: Cierre inmediato de paneles laterales (*drawers*) y diálogos modales.
  - `Cmd/Ctrl + K`: Apertura inmediata del buscador global.
- **Regla contra el Monocromatismo:** Queda terminantemente prohibido comunicar el estado de una expedición únicamente a través del color del texto o del fondo. Toda indicación de estado debe acompañarse obligatoriamente de:
  1. Texto semántico explícito (ej. *"PENDIENTE MATRÍCULA"*).
  2. Icono o punto indicador contrastado.
  3. Atributo `aria-label` o `role="status"` para lectores de pantalla.

---

## 7. REGLAS DE IMPLEMENTACIÓN PARA ANTIGRAVITY (FRONTEND)

Cualquier agente de IA o ingeniero de software que implemente o modifique vistas en DECA Light debe acatar las siguientes **reglas estrictas**:

1. **Lectura Previa Obligatoria:** Consultar este archivo (`DESIGN_SYSTEM.md`) antes de crear o editar cualquier archivo en `templates/`, `static/`, HTML o CSS.
2. **Inspección de Existencias:** Antes de crear una nueva clase CSS o un componente visual, comprobar si ya existe un token o patrón documentado aquí. Evitar duplicidades y estilos dispersos.
3. **Uso Exclusivo de Design Tokens:** Prohibido utilizar colores HEX o márgenes arbitrarios directamente en el código (*hardcoded*). Emplear siempre las variables CSS semánticas (`var(--color-...)`, `var(--radius-...)`).
4. **Cero Dependencias Innecesarias:**
   - La arquitectura de frontend establecida es **Server-Side Rendering con FastAPI + Jinja2 + HTMX**.
   - Prohibido instalar frameworks SPA pesados (React, Vue, Angular) o herramientas de build complejas (Webpack, Vite, npm masivo) a menos que se apruebe formalmente un ADR.
   - Se prioriza CSS puro estructurado y vanilla JavaScript para micro-interacciones (copiar portapapeles, atajos de teclado).
5. **Aislamiento de la Lógica de Negocio:** Ningún cambio cosmético o maquetación puede alterar el dominio (`src/domain/`), los servicios de validación legal ni la capa de persistencia relacional.
6. **Fidelidad al Dominio:** Prohibido inventar estados, campos o acciones que no existan en los enums del dominio (`ExpeditionStatus`, `DeCAStatus`, `VehicleType`).
7. **Verificación Multi-dispositivo:** Comprobar que cualquier nueva plantilla renderiza correctamente tanto en monitor de escritorio como en vista compacta de tablet.
8. **Ejecución de Pruebas:** Tras implementar componentes de interfaz, verificar que la suite de pruebas automatizadas (`pytest`) continúa ejecutándose con el 100% de éxito.
9. **Gobernanza del Documento:** `DESIGN_SYSTEM.md` es la **fuente de verdad visual** de DECA Light. Cualquier cambio en la dirección de diseño debe registrarse en este documento antes de implementarse en código.
