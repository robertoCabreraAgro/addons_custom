# 📋 GUÍA DE INSTALACIÓN Y VERIFICACIÓN - base_approval_sales

## 🎯 OBJETIVO COMPLETADO

**`base_approval_sales` es ahora la ÚNICA FUENTE DE VERDAD para aprobaciones de ventas**

Esta guía documenta el proceso completo de instalación, migración y verificación del módulo centralizado de aprobaciones de ventas.

---

## 📦 PRE-REQUISITOS

### Dependencias Obligatorias
- ✅ **base_approval**: Módulo base de aprobaciones (debe estar instalado)
- ✅ **sale**: Módulo de ventas de Odoo (core)
- ✅ **Odoo 18.0+**: Compatible con versión 18.2 saas
- ✅ **Permisos de Admin**: Para ejecutar post_init_hook

### Verificación de Dependencias
```bash
# Verificar que base_approval existe
python3 odoo-bin shell -d database_name <<EOF
try:
    env['approval.category'].search([], limit=1)
    print("✅ base_approval está disponible")
except:
    print("❌ base_approval NO está instalado")
EOF
```

---

## 🚀 PROCESO DE INSTALACIÓN

### Paso 1: Backup de Seguridad
```bash
# OBLIGATORIO: Backup antes de instalar
pg_dump -U odoo -d database_name > backup_before_approval_$(date +%Y%m%d_%H%M%S).sql
echo "✅ Backup creado: backup_before_approval_$(date +%Y%m%d_%H%M%S).sql"
```

### Paso 2: Instalación del Módulo
```bash
# Instalación con post_init_hook automático
python3 /home/sistemas4/instancias/odoo-bin \
    -c /home/sistemas4/instancias/odoo.conf \
    -d database_name \
    -i base_approval_sales \
    --stop-after-init

# Verificar logs de migración
tail -f /var/log/odoo/odoo.log | grep "base_approval_sales"
```

### Paso 3: Verificación de Instalación
```bash
# Script de verificación automática
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
# Verificar módulo instalado
module = env['ir.module.module'].search([('name', '=', 'base_approval_sales')])
print(f"Módulo instalado: {module.state}")

# Verificar post_init_hook ejecutado
logs = env['ir.logging'].search([
    ('name', '=', 'base_approval_sales.migration'),
    ('func', '=', 'post_init_hook')
], order='id desc', limit=1)

if logs:
    print("✅ Post-init hook ejecutado correctamente")
    print(f"Fecha: {logs.create_date}")
else:
    print("❌ Post-init hook no encontrado")

# Verificar estadísticas de migración
orders_total = env['sale.order'].search_count([])
orders_with_approval = env['sale.order'].search_count([('approval_request_id', '!=', False)])
orders_requiring = env['sale.order'].search_count([('require_approval', '=', True)])

print(f"📊 Estadísticas:")
print(f"  • Total órdenes: {orders_total}")
print(f"  • Con approval request: {orders_with_approval}")
print(f"  • Requieren aprobación: {orders_requiring}")
EOF
```

---

## 🔍 VERIFICACIÓN FUNCIONAL

### Test 1: Workflow Completo de Aprobación
```bash
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
# Test del workflow completo
partner = env.ref('base.res_partner_1')
product = env.ref('product.product_product_1')

# 1. Crear cotización
order = env['sale.order'].create({
    'partner_id': partner.id,
    'line_ids': [(0, 0, {
        'product_id': product.id,
        'product_uom_qty': 1,
        'price_unit': 100.0,
    })],
})

print(f"✅ Orden creada: {order.name}")
print(f"  • Requiere aprobación: {order.require_approval}")
print(f"  • Approval request: {bool(order.approval_request_id)}")
print(f"  • Estado: {order.state}")
print(f"  • Estado aprobación: {order.approval_state_display}")

# 2. Solicitar aprobación
try:
    order.action_request_approval()
    print(f"✅ Aprobación solicitada")
    print(f"  • Estado orden: {order.state}")
    print(f"  • Estado aprobación: {order.approval_state_display}")
except Exception as e:
    print(f"❌ Error al solicitar aprobación: {e}")

# 3. Intentar confirmar sin aprobación
try:
    order.action_confirm()
    print("❌ ERROR: Confirmó sin aprobación")
except Exception as e:
    print(f"✅ Correctamente bloqueado: {str(e)[:50]}...")

# Rollback para no afectar DB
env.cr.rollback()
EOF
```

### Test 2: Estados del Breadcrumb
```bash
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
# Verificar estados en español
order = env['sale.order'].search([], limit=1)
if order:
    state_field = order._fields['state']
    selections = dict(state_field.get_description(env)['selection'])

    print("📋 Estados del breadcrumb:")
    for key, value in selections.items():
        if key in ['draft', 'sent', 'pending_approval', 'sale', 'done', 'cancel']:
            print(f"  • {key}: {value}")

    # Verificar pending_approval existe
    if 'pending_approval' in selections:
        print(f"✅ Estado 'pending_approval': {selections['pending_approval']}")
    else:
        print("❌ Estado 'pending_approval' no encontrado")
else:
    print("No hay órdenes para verificar")
EOF
```

### Test 3: Verificar Neutralización de Lógica Externa
```bash
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
# Verificar que po_approval está desactivado
companies = env['res.company'].search([])
po_approval_active = companies.filtered('po_approval')

if po_approval_active:
    print(f"❌ po_approval activo en {len(po_approval_active)} empresas")
else:
    print("✅ po_approval desactivado en todas las empresas")

# Verificar override de métodos
order = env['sale.order'].search([], limit=1)
if order:
    # Test _approval_allowed
    allowed_before = order._approval_allowed()
    print(f"✅ _approval_allowed funcional: {allowed_before}")

    # Test _compute_approval_state (debe no hacer nada)
    original_state = order.approval_state
    order._compute_approval_state()
    if order.approval_state == original_state:
        print("✅ _compute_approval_state neutralizado")
    else:
        print("❌ _compute_approval_state aún activo")
EOF
```

---

## 🧪 EJECUCIÓN DE TESTS

### Tests Unitarios
```bash
# Ejecutar tests de integración
python3 /home/sistemas4/instancias/odoo-bin \
    -c /home/sistemas4/instancias/odoo.conf \
    -d test_database \
    --test-enable \
    --test-tags approval_integration \
    -u base_approval_sales \
    --stop-after-init

# Verificar resultados
echo "Revisar logs para resultados de tests"
```

### Tests de Performance
```bash
# Test de rendimiento con múltiples órdenes
python3 /home/sistemas4/instancias/odoo-bin \
    -c /home/sistemas4/instancias/odoo.conf \
    -d test_database \
    --test-enable \
    --test-tags approval_performance \
    -u base_approval_sales \
    --stop-after-init
```

---

## 🎨 VERIFICACIÓN DE UI

### 1. Verificar Breadcrumb Mejorado
**Manual en interfaz:**
1. Ir a **Ventas > Órdenes > Cotizaciones**
2. Crear nueva cotización
3. Verificar breadcrumb muestra: `draft → sent → pending_approval → sale`
4. Solicitar aprobación y verificar cambio visual

### 2. Verificar Indicadores Visuales
**Elementos a verificar:**
- ✅ Indicador de estado de aprobación debajo del breadcrumb
- ✅ Botones contextuales (Solicitar/Aprobar/Rechazar)
- ✅ Tab "🔐 Información de Aprobación"
- ✅ Columna "Estado de Aprobación" en vista lista
- ✅ Badges en vista kanban

### 3. Verificar Filtros y Agrupaciones
**En vista lista:**
- ✅ Filtro "🕐 En Espera de Aprobación"
- ✅ Filtro "📋 Mis Aprobaciones Pendientes"
- ✅ Agrupación por "Estado de Aprobación"

---

## ⚠️ SOLUCIÓN DE PROBLEMAS

### Problema: Post-init Hook No Ejecutado
```bash
# Ejecutar manualmente
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
from addons.base_approval_sales import post_init_hook
post_init_hook(env)
EOF
```

### Problema: Estados Inconsistentes
```bash
# Script de limpieza
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
# Órdenes en pending con approval aprobado
orders = env['sale.order'].search([
    ('state', '=', 'pending_approval'),
    ('approval_request_id.state', '=', 'approved')
])
orders.write({'state': 'draft'})
print(f"✅ Corregidas {len(orders)} órdenes")

# Órdenes en draft con approval pending
orders = env['sale.order'].search([
    ('state', '=', 'draft'),
    ('approval_request_id.state', '=', 'pending')
])
orders.write({'state': 'pending_approval'})
print(f"✅ Corregidas {len(orders)} órdenes")
EOF
```

### Problema: Approval Category No Existe
```bash
# Crear categoría manualmente
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
for company in env['res.company'].search([]):
    category = env['approval.category'].search([
        ('name', '=', 'Sales Order Approval'),
        ('company_id', '=', company.id),
    ])

    if not category:
        category = env['approval.category'].create({
            'name': 'Sales Order Approval',
            'company_id': company.id,
            'has_amount': 'required',
            'has_partner': 'required',
            'has_reference': 'required',
            'approval_minimum': 1,
            'automated_sequence': True,
            'sequence_code': 'SO-APPR-',
        })
        print(f"✅ Categoría creada para {company.name}")
EOF
```

---

## 🔄 ROLLBACK (Si es Necesario)

### Rollback Completo
```bash
# 1. Restaurar backup
pg_restore -U odoo -d database_name backup_before_approval_YYYYMMDD_HHMMSS.sql

# 2. O desinstalar módulo
python3 /home/sistemas4/instancias/odoo-bin \
    -c /home/sistemas4/instancias/odoo.conf \
    -d database_name \
    -u base_approval_sales \
    --stop-after-init

# El uninstall_hook limpiará automáticamente
```

---

## ✅ CHECKLIST FINAL DE VERIFICACIÓN

### Funcionalidad Core
- [ ] Todas las órdenes requieren aprobación (`require_approval = True`)
- [ ] Approval requests se crean automáticamente
- [ ] Estado `pending_approval` funciona en breadcrumb
- [ ] Workflow completo: draft → pending_approval → draft → sale
- [ ] Botones de aprobación aparecen contextualmente
- [ ] Validaciones impiden confirmación sin aprobación

### UI/UX
- [ ] Breadcrumb muestra "En Espera de Aprobación"
- [ ] Indicador visual de estado de aprobación
- [ ] Tab de información de aprobación
- [ ] Filtros de aprobación en vistas
- [ ] Traducciones en español funcionan

### Seguridad y Permisos
- [ ] Solo managers pueden aprobar/rechazar
- [ ] Salespersons pueden solicitar aprobación
- [ ] Permisos se calculan correctamente (`can_approve`, `can_reject`)

### Integración
- [ ] No conflictos con otros módulos
- [ ] po_approval desactivado
- [ ] Métodos core neutralizados
- [ ] Post-init hook ejecutado exitosamente

### Performance
- [ ] Creación masiva de órdenes funciona
- [ ] Tiempos de respuesta aceptables
- [ ] Sin errores en logs

---

## 📞 SOPORTE

### Logs de Diagnóstico
```bash
# Ver logs específicos del módulo
grep "base_approval_sales" /var/log/odoo/odoo.log | tail -20

# Ver logs de migración
python3 /home/sistemas4/instancias/odoo-bin shell -d database_name <<EOF
logs = env['ir.logging'].search([
    ('name', 'like', 'base_approval_sales%')
], order='id desc', limit=5)
for log in logs:
    print(f"{log.create_date}: {log.message}")
EOF
```

### Contacto
- **Módulo**: base_approval_sales v18.2.2.0.0
- **Compatibilidad**: Odoo 18.0 (saas-18.2)
- **Documentación**: `/addons/addons_custom/base_approval_sales/README.md`

---

**🎉 ¡INSTALACIÓN COMPLETADA! base_approval_sales ES AHORA LA ÚNICA FUENTE DE VERDAD PARA APROBACIONES DE VENTAS**