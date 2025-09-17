---
marp: true
theme: default
size: 16:9
paginate: true
backgroundColor: #ffffff
color: #333333
style: |
  section {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
  }
  h1 {
    color: #2c3e50;
    border-bottom: 3px solid #3498db;
    padding-bottom: 10px;
  }
  h2 {
    color: #34495e;
    border-left: 4px solid #3498db;
    padding-left: 15px;
  }
  .step {
    background-color: #e8f4fd;
    padding: 15px;
    border-left: 4px solid #3498db;
    margin: 10px 0;
  }
  .code {
    background-color: #f8f9fa;
    padding: 15px;
    border: 1px solid #e9ecef;
    border-radius: 5px;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    overflow-x: auto;
  }

  .code_compl{
    font-size: 9px;
  }

  .warning {
    background-color: #fff3cd;
    padding: 10px;
    border-left: 4px solid #ffc107;
    color: #856404;
  }
  .success {
    background-color: #d4edda;
    padding: 10px;
    border-left: 4px solid #28a745;
    color: #155724;
  }
  .info {
    background-color: #d1ecf1;
    padding: 10px;
    border-left: 4px solid #17a2b8;
    color: #0c5460;
  }

---

# Manual intensivo: Desarrollo de un módulo Odoo — Estate

Clase dirigida a estudiantes de nuevo ingreso: objetivo que al final de la sesión comprendan, modifiquen y amplíen un módulo Odoo real (`estate`).

Contenido: explicación técnica, ejemplos, pruebas rápidas y checklist de buenas prácticas.

---

## Lista de requisitos (lo que pides)

- Explicar cada carpeta y archivo del módulo.
- Describir el contenido de cada archivo (línea a línea cuando sea útil).
- Explicar métodos Python, decoradores y su uso en Odoo.
- Describir todas las importaciones y su propósito.
- Explicar las vistas XML: sintaxis, elementos y ejemplos.
- Explicar relaciones entre modelos (Many2one, One2many, Many2many).
- Explicar la conexión con la base de datos via ORM y SQL constraints.
- Explicar cómo se integra el módulo con Odoo (manifest, registro de datos, menús).
- Explicar seguridad: `ir.model.access.csv`, grupos, reglas (ir.rule).
- Crear presentación MARP con diseño empresarial y orientada a clase.

Estado: voy a enriquecer `manual_estate_marp.md` con una versión extensa y didáctica que cubra todos los puntos.

---

## Qué haré ahora

- Leer el módulo completo (ya hecho) y generar un manual paso a paso.
- Incluir ejemplos concretos extraídos de los archivos del módulo (`models/`, `views/`, `security/`, `wizard/`, `report/`).
- Añadir secciones de práctica: cómo instalar, probar y depurar.

Checkpoint: archivo `manual_estate_marp.md` será reemplazado por esta versión extendida.

---

## Introducción para estudiantes

En esta clase veremos cómo se estructura un módulo Odoo y por qué cada archivo existe. Aprenderás a:

- Mapear modelos a tablas de base de datos con el ORM.
- Crear vistas (XML) que controlan la interfaz.
- Implementar lógica de negocio segura y testeable.
- Gestionar permisos y publicar reportes QWeb.

Recomendación práctica: sigue el manual en paralelo con un entorno Odoo local (instalación de desarrollo).

---

## Carpeta raíz: archivos obligatorios

- `__init__.py`
  - Propósito: inicializar el paquete Python del módulo y exponer submódulos.
  - En este módulo: importa `models` y `wizard` con:
    - from . import models
    - from . import wizard
  - Por qué es importante: sin él, Odoo no cargará el paquete Python ni ejecutará las importaciones que registran modelos.

- `__manifest__.py`
  - Propósito: metadatos del módulo (nombre, versión, dependencias, archivos de datos, etc.).
  - Campos clave en tu manifiesto:
    - name, version, summary, category, depends
    - data: lista ordenada de XML/CSV que Odoo cargará al instalar el módulo.
    - installable/application/auto_install
  - Observación: el orden en `data` importa (seguridad antes que vistas; menús al final cuando hacen referencia a acciones declaradas previamente).

- `README.md`
  - Propósito: documentación de usuario/desarrollador. Aquí hay una descripción general del módulo y sus características.

---

## Carpeta `models/` — diseño de datos y lógica

Archivos principales en el módulo:

- `estate_property.py` (modelo principal)
  - Declaración: class EstateProperty(models.Model): _name = 'estate.property'
  - Campos: Char, Text, Date, Float, Integer, Boolean, Selection, Many2one, One2many, Many2many.
  - Tipos y ejemplos:
    - fields.Char(required=True) — texto corto, índice opcional.
    - fields.Float — valores numéricos con punto flotante.
    - fields.Selection([...]) — conjunto finito de opciones.
    - fields.Many2one('estate.property.type') — FK a otro modelo.
    - fields.One2many('estate.property.offer', 'property_id') — relación inversa (no guarda columna adicional en la tabla principal).

  - Métodos y decoradores explicados:
    - @api.depends('living_area', 'garden_area')
      - Uso: recalcular `total_area` cuando cambian campos dependientes.
      - Efecto: Odoo marca el campo como computado y lo recalcula en vistas/lecturas.
    - @api.onchange('garden')
      - Uso: actualizar valores en la UI antes de guardar.
      - No se ejecuta en creación vía `create` en el servidor, solo en formularios web.
    - @api.constrains('selling_price', 'expected_price')
      - Uso: validación a nivel servidor; lanza `UserError` si la regla falla.
    - def action_sold(self):
      - Tipo: métodos de acción (invocados desde botones XML con type="object").
      - Devuelven True o `ir.actions` si abren vistas.

  - _sql_constraints:
    - Se traducen a constraints en la tabla SQL (CHECK, UNIQUE) y evitan datos inválidos a nivel DB.
    - Ejemplo: ('check_expected_price_positive','CHECK(expected_price >= 0)', '...')

- `estate_property_offer.py` (ofertas)
  - Campos: price, status (Selection), partner_id (Many2one res.partner), validity, date_deadline (compute + inverse), property_id.
  - Decoradores relevantes:
    - @api.depends('create_date', 'validity') para calcular `date_deadline`.
    - inverse: convierte cambios manuales de la fecha en actualización del número de días (validity).
    - @api.constrains para validar precio mínimo.
  - Sobrescritura de `create(self, vals)`:
    - Siempre llamar a `super()` para mantener la lógica base.
    - Ejemplo aquí: cuando se crea una oferta, cambia el estado de la propiedad a `offer_received`.

- `estate_property_type.py` y `estate_property_tag.py`
  - Modelos sencillos para clasificar propiedades.
  - `One2many` en tipo: property_ids = fields.One2many('estate.property', 'property_type_id') — permite listar propiedades desde el tipo.

- `res_partner.py` (extiende `res.partner`)
  - Uso de `_inherit = 'res.partner'` para añadir `property_offers_ids = fields.One2many('estate.property.offer', 'partner_id')`.
  - Importante: extendiendo modelos core se crean columnas lógicas; la tabla es la misma (`res_partner`).

Concepto de tablas y nombres:
- `_name = 'estate.property'` → tabla SQL: `estate_property` (Odoo convierte puntos en guiones bajos).

---

## Decoradores y utilidades (resumen)

- from odoo import models, fields, api — import básico.
- @api.model: método que no requiere registros previos (ej. create desde código genérico).
- @api.depends: recalcula campos computados cuando cambian campos listados.
- @api.onchange: reacciona a cambios en UI antes de guardar.
- @api.constrains: validación a nivel servidor al guardar.

Errores y excepciones:
- from odoo.exceptions import UserError — lanzar errores amigables al usuario.

---

## Carpeta `views/` — cómo construir la interfaz

Vistas en este módulo:

- `estate_property_views.xml` contiene:
  - Vista lista (`<list>`), vista formulario (`<form>`), `header` con botones, `statusbar` y `notebook` con páginas.
  - Botones en `<header>`: <button name="action_sold" type="object"/> llaman a métodos Python del registro.
  - `field` attributes:
    - `invisible`, `readonly`, `widget`, `context`.
    - `context` define valores por defecto para creación desde esa relación.

- `estate_property_offer_views.xml`:
  - Vista con `action_accept_offer` y `action_refuse_offer` en el header.
  - `view_mode` en la acción: `list,form`.

- `inherited_views.xml`:
  - Uso de `inherit_id` y `xpath` para extender vistas core (`res.partner`).
  - `xpath` selecciona dónde insertar: e.g., antes de `page[@name='internal_notes']`.

XML: buenas prácticas
- Usar `record` con `id` para referenciar acciones/menus desde `views/estate_menus.xml`.
- Mantener las vistas pequeñas y con contexto claro.

---

## Menús y acciones (`views/estate_menus.xml`)

- `menuitem` declara entradas de menú. Atributos:
  - id, name, parent, action, sequence, web_icon
- Estructura típica: raíz (module root) → opciones → recursos (Properties, Configuration).

---

## Reportes QWeb (`report/`)

- `estate_property_report_views.xml` y `estate_property_report.xml` definen plantillas QWeb y la acción report.
- Plantilla QWeb usa construcción t-call, t-esc, t-foreach. Es HTML que Odoo convierte en PDF.

---

## Seguridad: `security/estate_security.xml` y `ir.model.access.csv`

Elementos clave:

- `res.groups`: define `group_estate_user` y `group_estate_manager`.
- `implied_ids`: hace que un grupo implique otro (herencia de permisos).
- `ir.rule` (record model `ir.rule`): `domain_force` restringe registros según expresiones de dominio.
  - Ejemplo: `[('salesperson_id', '=', user.id)]` — usuarios ven solo sus propias propiedades.

- `ir.model.access.csv` columnas:
  - id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
  - `group_id` puede ser vacío (permite a todos los usuarios) o apuntar a un grupo específico.
  - `perm_*` son 1/0 para permisos.

Notas de seguridad:
- Orden de carga: cargar `estate_security.xml` antes de las vistas para que los grupos existan cuando ir.model.access.csv se evalúe.
- Cuidado con `domain_force` combinado con `sudo()` — `sudo()` ignora reglas normales.

---

## Conexión con la base de datos y el ORM

- Cada modelo corresponde a una tabla SQL cuyo nombre es el `_name` con `.` → `_`.
- Operaciones comunes del ORM:
  - self.env['model.name'].search(domain)
  - self.env['model.name'].browse(ids)
  - create(vals), write(vals), unlink()
  - mapped('field') para colecciones

Ejemplo en código:
  - offer = self.env['estate.property.offer'].create({ 'price': 100 })
  - properties = self.env['estate.property'].search([('state', '=', 'new')])

Indexación y constraints:
- `_sql_constraints` produce índice/constraint SQL.
- Para búsquedas rápidas, crear `index=True` en fields.Char si se busca por texto frecuentemente.

---

## Permisos y flujo de seguridad (caso práctico)

Escenario: un `Estate User` solo debe ver sus propiedades y crear ofertas; un `Estate Manager` gestiona todo.

Implementación en el módulo:

- Grupos en `estate_security.xml`.
- Reglas `ir.rule` para filtrar por `salesperson_id`.
- Entradas en `ir.model.access.csv` que asignan permisos de lectura/escritura según grupo.

Verificación práctica:

1. Crear dos usuarios de prueba: `user_a` (Estate User) y `manager` (Estate Manager).
2. Asignar `salesperson_id` a `user_a` en algunas propiedades.
3. Con `user_a` iniciar sesión y verificar que sólo se muestran las propiedades propias.

---

## Debugging y pruebas rápidas

Comandos útiles (ejecutar en servidor de Odoo o terminal del desarrollador):

```bash
# Reiniciar Odoo y actualizar módulo (modo developer):
sudo systemctl restart odoo
# O alternativamente, actualizar módulo desde la línea de comandos (ajusta ruta a odoo-bin y config):
./odoo-bin -c /etc/odoo/odoo.conf -d mydb -u estate --stop-after-init

# Actualizar la lista de apps desde UI: Apps → Update Apps List → instalar "Real Estate"
```

Cómo probar código Python rápidamente:

- Usar el modo `--dev=reload` o ejecutar tests unitarios si se añaden.
- Añadir prints o _logger en módulos, pero preferir `logging.getLogger(__name__)`.

---

## Buenas prácticas y recomendaciones para estudiantes

- Separar lógica en métodos pequeños y documentados.
- Proteger métodos sensibles con permisos y `check_access_rule` cuando sea necesario.
- Usar `@api.constrains` + `_sql_constraints` para validaciones complementarias.
- Añadir tests unitarios: cubrir `create`, validaciones y acciones.
- Documentar cada archivo con un encabezado breve.

---

## Actividades prácticas para la clase (ejercicios)

1. Modificar `estate_property` para añadir campo `energy_rating = fields.Selection(...)` y mostrarlo en la vista.
2. Crear un nuevo `ir.rule` que permita a un grupo ver propiedades con `expected_price` menor a X.
3. Añadir un botón que envíe un correo al comprador al aceptar una oferta (usar `mail.template`).

Para cada ejercicio, definir:
- Contrato del cambio (inputs/outputs).
- Casos borde (sin buyer, precio nulo, permisos insuficientes).

---

## Soluciones y ejemplos prácticos

Aquí están las soluciones paso a paso para los ejercicios propuestos. Cada solución incluye: contrato (input/output), los cambios de código recomendados (ruta y snippet), cómo probar localmente y casos borde.

### Ejercicio 1 — Añadir `energy_rating`

Contrato:
- Input: un formulario de propiedad.
- Output: campo `energy_rating` guardado en la tabla `estate_property` y visible en vistas.

Cambios (archivo a editar): `models/estate_property.py`

Código de ejemplo (añadir al modelo `EstateProperty`):

```python
# ...existing code...
    energy_rating = fields.Selection(
        selection=[('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D'), ('e', 'E')],
        string='Energy Rating',
        default='c',
        help='Energy efficiency rating of the property'
    )
# ...existing code...
```

Y en la vista: `views/estate_property_views.xml` (añadir dentro del grupo `Property Details`):

```xml
<field name="energy_rating"/>
```

Cómo probar:
1. Actualizar el módulo en Odoo: Apps → Update Apps List → actualizar `estate` (o usar `-u estate`).
2. Abrir una propiedad y verificar que el campo aparece y se guarda.

Casos borde:
- Valor nulo: si se requiere que siempre tenga valor, usar `required=True`.
- Migración de datos: si ya existen propiedades, elegir default razonable.

---

### Ejercicio 2 — Regla `ir.rule` por `expected_price` < X

Contrato:
- Input: grupo de usuarios `group_estate_price_limit` y un umbral X.
- Output: los usuarios de ese grupo sólo verán propiedades cuya `expected_price` sea menor que X.

Pasos prácticos:
1. Definir un grupo en `security/estate_security.xml` (si no existe):

```xml
<record id="group_estate_price_limit" model="res.groups">
  <field name="name">Estate Price Limit</field>
  <field name="category_id" ref="base.module_category_sales"/>
  <field name="implied_ids" eval="[(4, ref('group_estate_user'))]"/>
</record>
```

2. Añadir una regla `ir.rule` dinámicamente o fija. Ejemplo fijo en `security/estate_security.xml`:

```xml
<record id="estate_price_limit_rule" model="ir.rule">
  <field name="name">Properties under price limit</field>
  <field name="model_id" ref="model_estate_property"/>
  <!-- dominio que filtra expected_price menor que 100000 -->
  <field name="domain_force">[('expected_price','&lt;', 100000)]</field>
  <field name="groups" eval="[(4, ref('group_estate_price_limit'))]"/>
</record>
```

Nota: el valor 100000 es un ejemplo; para hacerlo configurable puede crearse un `res.config.settings` y construir la regla vía código en un `data` post-init.

Cómo probar:
1. Asignar un usuario al grupo `Estate Price Limit`.
2. Crear propiedades con `expected_price` por encima y por debajo del umbral.
3. Iniciar sesión con el usuario del grupo y verificar que sólo ve las propiedades filtradas.

Casos borde:
- Usuarios con varios grupos: las reglas se combinan; un usuario con manager podría ver todo.
- Uso de `sudo()`: ignora reglas; no usar `sudo()` en búsquedas mostradas en UI si no se desea saltarlas.

---

### Ejercicio 3 — Enviar correo al aceptar oferta

Contrato:
- Input: acción `action_accept_offer` en `estate.property.offer`.
- Output: enviar un correo al `partner_id` (comprador) usando una plantilla `mail.template` y registrar la acción.

Pasos prácticos:
1. Crear una plantilla de correo en un XML `data` (por ejemplo `data/mail_template.xml`):

```xml
<odoo>
  <data noupdate="1">
    <record id="email_template_offer_accepted" model="mail.template">
      <field name="name">Offer Accepted Notification</field>
      <field name="model_id" ref="model_estate_property_offer"/>
      <field name="subject">Your offer has been accepted</field>
      <field name="email_from">${(object.property_id.salesperson_id.email or 'noreply@example.com')|safe}</field>
      <field name="body_html"><![CDATA[
        <p>Dear <t t-esc="object.partner_id.name"/>,</p>
        <p>Your offer of <strong><t t-esc="'%.2f' % object.price"/></strong> for the property <t t-esc="object.property_id.name"/> has been accepted.</p>
        <p>Regards,<br/><t t-esc="object.property_id.salesperson_id.name"/></p>
      ]]></field>
    </record>
  </data>
</odoo>
```

2. Modificar `models/estate_property_offer.py` en `action_accept_offer` para enviar el correo:

```python
from odoo import api, _

    def action_accept_offer(self):
        template = self.env.ref('estate.email_template_offer_accepted', raise_if_not_found=False)
        for offer in self:
            if offer.status in ['accepted', 'refused']:
                raise UserError("This offer has already been accepted or refused.")
            if offer.property_id.has_accepted_offer:
                raise UserError("This property already has an accepted offer.")
            offer.status = 'accepted'
            offer.property_id.state = 'offer_accepted'
            offer.property_id.selling_price = offer.price
            offer.property_id.buyer_id = offer.partner_id
            # enviar correo si plantilla existe
            if template and offer.partner_id.email:
                template.with_context(lang=offer.partner_id.lang).send_mail(offer.id, force_send=True)

```

Cómo probar:
1. Añadir la plantilla al `data` en `__manifest__.py`.
2. Crear una oferta de prueba con `partner_id` que tenga email.
3. Ejecutar `Accept Offer` y verificar en la bandeja de salida que el correo fue enviado (o revisar logs si `force_send=True`).

Casos borde:
- `partner_id.email` vacío: evitar excepción comprobando su existencia.
- Plantilla no encontrada: usar `raise_if_not_found=False` y manejar `None`.

---

## Código adicional y pruebas unitarias (sugerencia)

Para cada cambio importante, añade pruebas unitarias. Ejemplo (esqueleto) para `tests/test_offer.py` usando framework de pruebas de Odoo:

```python
def test_offer_accept_sets_property_sold(env):
    Property = env['estate.property']
    Offer = env['estate.property.offer']
    # ... crear property y partner ...
    offer = Offer.create({'price': 100, 'partner_id': partner.id, 'property_id': property.id})
    offer.action_accept_offer()
    assert offer.status == 'accepted'
    assert property.selling_price == 100
```

Recomendación: agregar carpetas `tests/` y ejecutar la suite de Odoo para verificar integridad.

---

He añadido estas soluciones y ejemplos dentro de la presentación MARP. Puedo ahora:

- Generar la diapositiva con las soluciones resueltas (ya añadida).
- Crear los archivos XML/PY reales en el módulo si quieres que aplique los cambios directamente al código.


## Cierre: qué entrego y próximos pasos

Entregable: esta presentación MARP `manual_estate_marp.md` actualizada con explicaciones y ejercicios.

Próximos pasos sugeridos:

- Añadir una carpeta `tests/` con unit tests (pytest-odoo o framework integrado).
- Mejorar UI (assets en `static/` y QWeb widgets).
- Internacionalizar textos (`i18n/*.po`) y probar traducciones.

---

## Recursos y lecturas recomendadas

- Documentación oficial Odoo: Models, Fields, API decorators, Views, QWeb, Security.
- Ejemplos de módulos en OCA (Open Community Association) para buenas prácticas.

---

Gracias — la presentación ahora es extensa y orientada a una clase universitaria; dime si quieres que:

- Añada diapositivas de solución a los ejercicios.
- Incluya tests de ejemplo.
- Genere un PDF directo desde MARP.
