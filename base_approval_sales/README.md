# Base Approval Sales

## Descripción
Módulo que integra exclusivamente el sistema de aprobaciones (`base_approval`) con las órdenes de venta (`sale.order`) de Odoo, implementando un workflow completo de aprobación con estados extendidos en la barra de estado.

## Funcionalidades Principales

### Core
- **Aprobación Universal**: TODAS las cotizaciones requieren aprobación obligatoria
- **Estados Extendidos**: Extensión del campo `state` para incluir estados de aprobación
- **Workflow Integrado**: Estados de aprobación integrados en la barra de estado principal
- **Botones Inteligentes**: Lógica de visibilidad corregida usando sintaxis `attrs` compatible

### Estados en la Barra de Estado
- **draft, sent**: Estados normales de cotización
- **pending_approval**: Cotización requiere aprobación y está pendiente
- **approved**: Cotización aprobada y lista para confirmar
- **cancel**: Cotización cancelada

### Lógica de Botones (Sintaxis `attrs`)
- **Botón "Confirm"**: Invisible si no está en estado `approved` o si está pendiente de aprobación
- **Botón "Solicitar Aprobación"**: Visible solo para usuarios con grupo `sales_team.group_sale_salesman` en estados `draft/sent` sin solicitud previa
- **Sintaxis**: Usa expresiones `attrs` con operadores `|` y `&` para compatibilidad con Odoo clásico

## Estados de Aprobación

| Estado Sale Order | Texto en Statusbar | Descripción |
|---|---|---|
| `draft` | Borrador | Sin solicitud de aprobación |
| `sent` | Presupuesto Enviado | Sin solicitud de aprobación |
| `pending_approval` | En Espera de Aprobación | Esperando decisión del aprobador |
| `approved` | Aprobado | Listo para confirmar |
| `sale` | Orden de Venta | Confirmado |
| `cancel` | Cancelado | Cancelado |

## Flujo de Estados

```
CREAR → [draft]
   ↓
ENVIAR → [sent]
   ↓
SOLICITAR APROBACIÓN → [pending_approval]
   ↓
APROBAR → [approved]
   ↓
CONFIRMAR → [sale]
```

## Dependencias
- `base_approval`: Módulo base de aprobaciones (custom addon)
- `sale`: Módulo de ventas de Odoo

**Nota**: Este módulo NO depende de `purchase` ni extiende `purchase.order`. Es exclusivamente para órdenes de venta.

## Instalación y Actualización

```bash
# Para instalación nueva
python3 odoo-bin -i base_approval_sales -d database_name

# Para actualización (UI mejorada)
python3 odoo-bin -u base_approval_sales -d database_name

# Ejecutar pruebas
python3 odoo-bin --test-enable --test-tags approval_ui -d test_database -u base_approval_sales
```

## Archivos Principales

### Modelos
- `models/sale_order.py`: Lógica principal y campo `approval_state_display`

### Vistas
- `views/sale_order_views.xml`: Vistas mejoradas con indicadores visuales

### Estilos
- `static/src/css/approval_styles.css`: CSS personalizado para UI

### Datos
- `data/approval_category_data.xml`: Categoría de aprobación por defecto

### Pruebas
- `tests/test_approval_ui.py`: Pruebas para funcionalidad de UI

## Vistas Implementadas

### Vista Formulario
- ✅ Statusbar extendido con estados `pending_approval` y `approved`
- ✅ Indicador visual de estado de aprobación
- ✅ Botones con lógica corregida usando sintaxis `attrs`
- ✅ Tab de información de aprobación con campos relevantes

### Vista Lista (Tree)
- ✅ Columna "Estado de Aprobación" con badge de colores
- ✅ Decoraciones visuales para estados

### Vista Kanban
- ✅ Indicadores visuales con badge widget
- ✅ Botones de acción para aprobar/rechazar

### Vista Búsqueda
- ✅ Filtros específicos para cada estado de aprobación
- ✅ Filtros para aprobaciones pendientes del usuario actual

## Implementación Técnica

### Campos Principales (Sales Only)
```python
# Relación directa con approval.request
approval_request_ref = fields.Many2one(
    'approval.request',
    string='Approval Request',
    help="Linked approval request for this sales order",
    copy=False,
    readonly=True,
)

# Aprobación requerida por defecto
require_approval = fields.Boolean(
    string='Requiere Aprobación',
    default=True,
    help="All sales orders require approval by default",
)

# Estados extendidos en sale.order
state = fields.Selection(
    selection_add=[
        ('pending_approval', 'En Espera de Aprobación'),
        ('approved', 'Aprobado'),
    ]
)

# Estado legible computado
approval_state_display = fields.Char(
    string='Estado de Aprobación',
    compute='_compute_approval_state',
    help="Current approval state in Spanish",
)
```

### Lógica de Botones con attrs (Odoo Compatible)
```xml
<!-- Botón Confirmar: Solo visible en estado 'approved' -->
<button name="action_confirm"
        attrs="{'invisible': ['|', ('state', 'not in', ('approved',)), '&amp;', ('require_approval', '=', True), ('state', '=', 'pending_approval')]}"/>

<!-- Botón Solicitar: Visible en draft/sent sin solicitud previa -->
<button name="action_request_approval"
        attrs="{'invisible': ['|', '|', '|', ('require_approval', '=', False), ('state', 'not in', ('draft', 'sent')), ('approval_request_ref', '!=', False), ('state', '=', 'pending_approval')]}"
        groups="sales_team.group_sale_salesman"/>

<!-- Campos con visibilidad condicional -->
<field name="approval_state_display"
       attrs="{'invisible': [('require_approval', '=', False)]}"/>
<group attrs="{'invisible': ['|', ('state', 'not in', ('pending_approval', 'draft', 'approved')), ('approval_request_ref', '=', False)]}">
    <!-- Contenido del grupo -->
</group>
```

## Notas Técnicas

### Compatibilidad y Diseño
- ✅ **Exclusivamente Sales** - Solo extiende `sale.order`, sin referencias a Purchase
- ✅ **Sintaxis attrs** - Usa expresiones `attrs` con operadores `|` y `&` para máxima compatibilidad
- ✅ **Many2one directo** - Relación directa con `approval.request` sin referencias string
- ✅ **Widget badge** - Sin dependencias OWL, usando widgets nativos
- ✅ **Estados extendidos** - Integración completa en statusbar

### Arquitectura Limpia
- **Dependencias mínimas**: Solo `sale` y `base_approval`
- **Sin Purchase**: Eliminadas todas las referencias a `purchase.order` y módulo `purchase`
- **Campos optimizados**: `approval_request_ref` como Many2one directo
- **Aprobación universal**: Todas las cotizaciones requieren aprobación obligatoria

### Convenciones
- Sigue estándares de AgroMarin para desarrollo
- Campos computados con dependencias optimizadas usando relaciones directas
- Traducciones dinámicas en español
- Estados sincronizados con workflow de aprobación
- Código limpio sin métodos helper innecesarios