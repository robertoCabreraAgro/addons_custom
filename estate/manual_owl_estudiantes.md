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

# Manual de Desarrollo OWL
## Creando el módulo `owl_practica_new` paso a paso

**Guía completa para estudiantes**
*Desarrollo Frontend con OWL en Odoo 18*

**Autor**: JEM  
**Fecha**: Septiembre 2025  
**Nivel**: Intermedio

---

# Índice del Manual

1. **Conceptos fundamentales** - ¿Qué es OWL?
2. **Preparación del entorno** - Requisitos y configuración
3. **Paso 1**: Crear la estructura básica del módulo
4. **Paso 2**: Configurar el manifest
5. **Paso 3**: Crear el componente principal
6. **Paso 4**: Desarrollar módulos especializados
7. **Paso 5**: Crear controladores backend
8. **Paso 6**: Configurar templates XML
9. **Paso 7**: Integrar estilos CSS
10. **Paso 8**: Registrar y probar el módulo
11. **Troubleshooting** - Solución de problemas comunes
12. **Mejores prácticas** - Consejos avanzados

---

# Conceptos Fundamentales

## ¿Qué es OWL?

<div class="info">
<strong>OWL (Odoo Web Library)</strong> es el framework frontend moderno de Odoo que permite crear interfaces de usuario interactivas y reactivas usando componentes.
</div>

### Ventajas de OWL:
- ✅ **Componentes reutilizables** - Escribes una vez, usas muchas veces
- ✅ **Estado reactivo** - Los cambios se reflejan automáticamente en la UI
- ✅ **Mejor performance** - Virtual DOM y optimizaciones automáticas
- ✅ **Desarrollo moderno** - Similar a React/Vue.js

### Conceptos clave que aprenderás:
- **Componentes** - Bloques de código reutilizables
- **Estado (State)** - Datos que cambian en tiempo real
- **Hooks** - Funciones especiales para el ciclo de vida
- **Templates** - Plantillas XML para la interfaz

---

# Preparación del Entorno

## Requisitos previos:

<div class="step">
<strong>Paso 0.1:</strong> Verifica que tengas Odoo 18 instalado y funcionando
</div>

<div class="code">
# Verificar versión de Odoo
./odoo-bin --version

# Debe mostrar: odoo 18.x.x
</div>

<div class="step">
<strong>Paso 0.2:</strong> Asegúrate de tener acceso a los addons personalizados
</div>

<pre>
<div class="code">
# Tu estructura debe verse así:
addons/
├── addons_custom/  ← Aquí trabajaremos
├── enterprise/
└── odoo/
</div>
</pre>

<div class="warning">
<strong>⚠️ Importante:</strong> Antes de comenzar, asegúrate de tener permisos de escritura en la carpeta addons_custom y que Odoo esté configurado para cargar módulos desde esa ubicación.
</div>

---

# Paso 1: Crear la Estructura Básica

## 1.1 Crear el directorio del módulo

<div class="step">
<strong>Objetivo:</strong> Crear la estructura de carpetas necesaria para nuestro módulo OWL
</div>

<div class="code"">
# Navegar a la carpeta de addons personalizados
cd addons/addons_custom/

# Crear el directorio principal del módulo
mkdir owl_practica_new

# Crear las subcarpetas necesarias
cd owl_practica_new
mkdir static static/src static/src/js static/src/xml static/src/css
mkdir controllers views
</div>

---

## 1.2 Estructura final esperada:

<pre>
<div class="code">
owl_practica_new/
├── __init__.py                 # Archivo de inicialización Python
├── __manifest__.py             # Configuración del módulo
├── controllers/                # Endpoints backend (API)
│   ├── __init__.py
│   └── controllers.py
├── static/src/                 # Archivos frontend
│   ├── css/
│   │   └── practica_widget.css
│   ├── js/                     # Componentes OWL
│   │   ├── client_action.js
│   │   ├── main_widget.js
│   │   ├── module_basic_controls.js
│   │   ├── module_database_data.js
│   │   └── module_analytics.js
│   └── xml/                    # Templates
│       └── *.xml
└── views/                      # Menús y acciones
    ├── practica_action.xml
    └── practica_menu.xml
</div>
</pre>
---

# Paso 2: Configurar el Manifest

## 2.1 Crear __init__.py

<div class="step">
<strong>¿Qué hace?</strong> Le dice a Python que esta carpeta es un módulo
</div>

<div class="code">
# Crear archivo: owl_practica_new/__init__.py
<br>
from . import controllers
</div>

## 2.2 Crear __manifest__.py

<div class="step">
<strong>¿Qué hace?</strong> Define la configuración, dependencias y assets del módulo
</div>

---

<pre>
<div class="code_compl">
# Crear archivo: owl_practica_new/__manifest__.py
{
    "name": "OWL Practica New",
    "version": "2.6",
    "summary": "Módulo de práctica para OWL widget",
    "description": """
        Tutorial paso a paso para aprender OWL:
        - Componentes básicos y estado reactivo
        - Integración con base de datos
        - Gráficos interactivos con Chart.js
        - Arquitectura modular y escalable
    """,
    "category": "Tools",
    "author": "Tu Nombre",
    "depends": ["base", "web"],  # Dependencias mínimas
    "data": [
        "views/practica_action.xml",
        "views/practica_menu.xml"
    ],
    "assets": {
        "web.assets_backend": [
            # Librería externa para gráficos
            "https://cdn.jsdelivr.net/npm/chart.js",
            
            # CSS (estilos)
            "owl_practica_new/static/src/css/practica_widget.css",
            
            # JavaScript (¡ORDEN IMPORTANTE!)
            "owl_practica_new/static/src/js/module_basic_controls.js",
            "owl_practica_new/static/src/js/module_database_data.js", 
            "owl_practica_new/static/src/js/module_analytics.js",
            "owl_practica_new/static/src/js/main_widget.js",
            "owl_practica_new/static/src/js/client_action.js",

            # Templates XML
            "owl_practica_new/static/src/xml/*.xml",
        ],
    },
    "installable": True,
    "application": False,  # False = módulo, True = aplicación independiente
}
</div>
</pre>
---

# Paso 3: Crear el Componente Principal

## 3.1 ¿Qué es un componente OWL?

<div class="info">
Un <strong>componente</strong> es como un bloque de LEGO que puedes reutilizar. Tiene:
<br>• <strong>Lógica</strong> (JavaScript) - Qué hace
<br>• <strong>Interfaz</strong> (XML) - Cómo se ve
<br>• <strong>Estado</strong> - Qué datos maneja
</div>

## 3.2 Crear main_widget.js


<div class="step">


<strong>¿Qué hace?</strong> Es el componente "padre" que contiene y organiza otros componentes
</div>

---

<pre>
<div class="code" class="code_compl">
// Crear archivo: static/src/js/main_widget.js

// 1. Importar lo que necesitamos de OWL
import { Component } from "@odoo/owl";

// 2. Importar nuestros componentes hijos
import { BasicControlsWidget } from "./module_basic_controls";
import { DatabaseDataWidget } from "./module_database_data";
import { AnalyticsWidget } from "./module_analytics";

// 3. Crear nuestro componente principal
export class PracticaNewWidget extends Component {
    // 4. Definir qué template XML usar
    static template = "owl_practica_new.MainDashboard";
    
    // 5. Registrar componentes hijos que usaremos
    static components = { 
        BasicControlsWidget, 
        DatabaseDataWidget, 
        AnalyticsWidget
    };
    
    // 6. Función setup - se ejecuta al crear el componente
    setup() {
        console.log("📱 MainDashboard cargado con todos los módulos");
        // Aquí puedes inicializar variables, eventos, etc.
    }
}
</div>

<div class="success">
<strong>💡 Concepto clave:</strong> Este componente es como un "contenedor" que organiza otros componentes más pequeños. Es el patrón de composición.
</div>
</pre>
---

# Paso 4.1: Módulo de Controles Básicos

## 4.1 ¿Qué aprenderemos aquí?

<div class="info">
En este módulo aprenderás sobre <strong>estado reactivo</strong> - cuando cambias una variable, la interfaz se actualiza automáticamente.
</div>


<div class="warning">
<strong>⚠️ Concepto importante:</strong> <code>useState</code> hace que cualquier cambio en <code>this.state</code> actualice automáticamente la interfaz. ¡No necesitas manipular el DOM manualmente!
</div>

---
## 4.2 Crear module_basic_controls.js
<div class="info">
// Crear archivo: static/src/js/module_basic_controls.js
</div>
<div class="code">

// 1. Importar Component y useState de OWL
import { Component, useState } from "@odoo/owl";

// 2. Crear el componente
export class BasicControlsWidget extends Component {
    // 3. Definir el template XML
    static template = "owl_practica_new.BasicControls";
    
    // 4. Función setup - configuración inicial
    setup() {
        // 5. Crear estado reactivo
        this.state = useState({ 
            count: 0,                    // Contador que inicia en 0
            message: "¡Hola desde OWL!"  // Mensaje inicial
        });
        
        console.log("🎮 BasicControlsWidget inicializado");
    }
    
    // 6. Método para incrementar contador
    increment() {
        this.state.count++;  // ✨ ¡Magia! La UI se actualiza sola
        console.log(`📊 Contador: ${this.state.count}`);
    }
    
    // 7. Método para cambiar mensaje
    changeMessage() {
        this.state.message = `Mensaje actualizado ${this.state.count} veces`;
        console.log(`💬 Mensaje: ${this.state.message}`);
    }
}
</div>

---

# Paso 4.2: Módulo de Datos de Base de Datos

## 4.3 ¿Qué aprenderemos aquí?

<div class="info">
Aprenderás a hacer peticiones <strong>asíncronas</strong> al backend para obtener datos reales de la base de datos de Odoo.
</div>

---

## 4.4 Crear module_database_data.js (Parte 1)

<div class="info">
Crear archivo: static/src/js/module_database_data.js
</div>

<div class="code">

// 1. Importar lo necesario
import { Component, useState, onWillStart } from "@odoo/owl";

export class DatabaseDataWidget extends Component {
    static template = "owl_practica_new.DatabaseData";
    
    setup() {
        // 2. Estado para guardar los datos
        this.state = useState({
            partners: [],           // Lista de contactos
            products: [],          // Lista de productos  
            loading: true,         // Indicador de carga
            activeTab: 'partners'  // Pestaña activa
        });
        
        // 3. Hook que se ejecuta ANTES de mostrar el componente
        onWillStart(() => this.loadData());
        console.log("💾 DatabaseDataWidget inicializado");
    }
    
    // 4. Función para cargar datos
    async loadData() {
        try {
            console.log("🔄 Cargando datos...");
            
            // 5. Hacer peticiones paralelas (más rápido)
            const [partners, products] = await Promise.all([
                this.makeRequest('/practica/get_partners'),
                this.makeRequest('/practica/get_products')
            ]);
</div>

---

<div class="code">

            // 6. Actualizar estado con los datos
            Object.assign(this.state, {
                partners: partners?.data || [],
                products: products?.data || [],
                loading: false
            });
            
            console.log(`✅ Datos cargados: ${this.state.partners.length} contactos, ${this.state.products.length} productos`);
            
        } catch (error) {
            console.error("❌ Error cargando datos:", error);
            this.state.loading = false;
        }
    }
</div>

---

# Paso 4.2: Continuación - Peticiones HTTP

<div class="code">
    // 7. Función helper para hacer peticiones HTTP
    async makeRequest(endpoint) {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: "2.0",    // Protocolo que usa Odoo
                method: "call",
                params: {},
                id: Math.random()  // ID único para la petición
            })
        });
        
        // 8. Verificar si la respuesta es exitosa
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // 9. Verificar errores del servidor
        if (data.error) {
            throw new Error(data.error.message);
        }
        
        console.log(`📡 Petición exitosa: ${endpoint}`);
        return data.result;
    }
    
    // 10. Función para cambiar de pestaña
    switchTab(tabName) {
        this.state.activeTab = tabName;
        console.log(`🔄 Pestaña cambiada a: ${tabName}`);
    }
}
</div>

<div class="success">
<strong>💡 Conceptos clave aprendidos:</strong>
<br>• <strong>async/await</strong> - Para operaciones asíncronas
<br>• <strong>Promise.all</strong> - Para ejecutar peticiones en paralelo
<br>• <strong>fetch API</strong> - Para comunicarse con el backend
<br>• <strong>JSON-RPC</strong> - Protocolo de comunicación de Odoo
</div>

---

# Paso 4.3: Módulo de Analytics y Gráficos

## 4.5 ¿Qué aprenderemos aquí?

<div class="info">
Aprenderás a integrar librerías externas (Chart.js) con OWL y crear gráficos interactivos con datos reales.
</div>

---

## 4.6 Crear module_analytics.js (Parte 1)

<div class="code">
// Crear archivo: static/src/js/module_analytics.js

import { Component, useState, onWillStart } from "@odoo/owl";

export class AnalyticsWidget extends Component {
    static template = "owl_practica_new.Analytics";
    
    setup() {
        // 1. Estado para los gráficos
        this.state = useState({
            chartData: null,        // Datos para los gráficos
            loading: true,          // Estado de carga
            activeChart: 'categories' // Gráfico activo
        });
        
        // 2. Variable para mantener referencia al gráfico actual
        this.currentChart = null;
        
        // 3. Configuraciones para diferentes tipos de gráficos
        this.chartConfigs = {
            categories: {
                type: 'bar',
                getLabels: (data) => data.categories.map(c => c.category || 'Sin categoría'),
                getData: (data) => data.categories.map(c => c.product_count),
                colors: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0'],
                title: 'Productos por Categoría'
            },
            partners: {
                type: 'doughnut',
                getLabels: (data) => data.partners.map(p => p.partner_type),
                getData: (data) => data.partners.map(p => p.partner_count),
                colors: ['#36A2EB', '#FF6384'],
                title: 'Distribución de Contactos'
            },
</div>

---

<div class="code_compl">

            prices: {
                type: 'bar',
                getLabels: (data) => data.price_ranges.map(p => p.price_range),
                getData: (data) => data.price_ranges.map(p => p.product_count),
                colors: '#4BC0C0',
                title: 'Productos por Rango de Precio'
            }
        };
        
        onWillStart(() => this.loadChartData());
        console.log("📊 AnalyticsWidget inicializado");
    }
</div>

---

# Paso 4.3: Continuación - Funciones del Analytics


<div class="info">
    // 4. Cargar datos para gráficos
</div>
<pre>
<div class="code_compl">
    async loadChartData() {
        try {
            const response = await fetch('/practica/get_chart_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call", 
                    params: {},
                    id: Math.random()
                })
            });
            
            const data = await response.json();
            this.state.chartData = data.result?.data;
            this.state.loading = false;
            
            // 5. Esperar un poco para que el DOM esté listo
            setTimeout(() => this.createChart(), 300);
            console.log("📈 Datos de gráficos cargados");
            
        } catch (error) {
            console.error("❌ Error cargando datos de gráficos:", error);
            this.state.loading = false;
        }
    }
    
    // 6. Cambiar entre diferentes gráficos
    switchChart(chartName) {
        this.state.activeChart = chartName;
        setTimeout(() => this.createChart(), 100);
        console.log(`📊 Gráfico cambiado a: ${chartName}`);
    }
    
    // 7. Crear el gráfico con Chart.js
    createChart() {
        // Verificar que tengamos datos y Chart.js esté cargado
        if (!this.state.chartData || !window.Chart) {
            console.warn("⚠️ Creación de gráfico omitida: faltan datos o Chart.js");
            return;
        }
        
        // 8. Destruir gráfico anterior si existe
        if (this.currentChart) {
            this.currentChart.destroy();
        }
</div>
</pre>
---

# Paso 4.3: Continuación - Crear Gráfico
<div class="info">
        // 9. Obtener configuración del gráfico activo
</div>

<div class="code_compl">
        const config = this.chartConfigs[this.state.activeChart];
        const canvas = document.getElementById('analyticsChart');
        
        if (!canvas) {
            console.warn("⚠️ Canvas no encontrado");
            return;
        }
        // 10. Crear nuevo gráfico
        this.currentChart = new Chart(canvas, {
            type: config.type,
            data: {
                labels: config.getLabels(this.state.chartData),
                datasets: [{
                    label: config.title,
                    data: config.getData(this.state.chartData),
                    backgroundColor: config.colors,
                    borderColor: config.colors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: config.title
                    }
                },
                scales: config.type === 'bar' ? {
                    y: { beginAtZero: true }
                } : {}
            }
        });
        
        console.log(`✅ Gráfico creado: ${config.title}`);
    }
}
</div>

<div class="warning">
<strong>⚠️ Concepto importante:</strong> Siempre destruye gráficos anteriores con <code>.destroy()</code> para evitar memory leaks. Los timeouts dan tiempo al DOM para actualizarse.
</div>

---

# Paso 5: Crear Controladores Backend

## 5.1 ¿Para qué sirven los controladores?

<div class="info">
Los <strong>controladores</strong> son como "camareros" que traen datos de la base de datos al frontend. Crean endpoints (URLs) que el frontend puede llamar.
</div>

## 5.2 Crear controllers/__init__.py

<div class="code">
# Crear archivo: controllers/__init__.py
from . import controllers
</div>

## 5.3 Crear controllers/controllers.py (Parte 1)

<div class="code">
# Crear archivo: controllers/controllers.py

# 1. Importar lo necesario de Odoo
from odoo import http
from odoo.http import request
import json

# 2. Crear la clase controladora
class PracticaController(http.Controller):

    # 3. Endpoint para obtener contactos
    @http.route('/practica/get_partners', type='json', auth='user')
    def get_partners(self, **kwargs):
        """
        Obtiene contactos de la base de datos
        - type='json': Acepta peticiones JSON
        - auth='user': Usuario debe estar autenticado
        """
        try:
            # 4. Usar el ORM de Odoo para consultar datos
            partners = request.env['res.partner'].search_read(
                domain=[],  # [] = sin filtros, trae todos
                fields=['id', 'name', 'email', 'phone', 'is_company'],
                # limit=50  # Opcional: limitar resultados
            )
            
            # 5. Retornar respuesta exitosa
            return {
                'status': 'success',
                'data': partners
            }
            
        except Exception as e:
            # 6. Manejar errores
            return {
                'status': 'error', 
                'message': str(e)
            }
</div>

---

# Paso 5: Continuación - Más Endpoints

<div class="code">
    # 7. Endpoint para obtener productos
    @http.route('/practica/get_products', type='json', auth='user')
    def get_products(self, **kwargs):
        """Obtiene productos que se pueden vender"""
        try:
            products = request.env['product.product'].search_read(
                domain=[('sale_ok', '=', True)],  # Solo productos vendibles
                fields=['id', 'name', 'list_price', 'categ_id'],
                limit=50  # Limitar a 50 para performance
            )
            
            return {
                'status': 'success',
                'data': products
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    # 8. Endpoint para datos de gráficos
    @http.route('/practica/get_chart_data', type='json', auth='user')
    def get_chart_data(self, **kwargs):
        """Obtiene datos agregados para gráficos"""
        try:
            # 9. Consulta SQL optimizada para categorías
            categories_query = """
                SELECT pc.name as category, COUNT(pp.id) as product_count
                FROM product_category pc
                LEFT JOIN product_template pt ON pt.categ_id = pc.id
                LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
                WHERE pt.sale_ok = true
                GROUP BY pc.id, pc.name
                ORDER BY product_count DESC
                LIMIT 10
            """
            
            # 10. Ejecutar consulta
            request.env.cr.execute(categories_query)
            categories = request.env.cr.dictfetchall()
</div>

---

# Paso 5: Continuación - Datos para Gráficos

<div class="code">
            # 11. Datos para gráfico de contactos
            partners_query = """
                SELECT 
                    CASE WHEN is_company THEN 'Empresas' ELSE 'Personas' END as partner_type,
                    COUNT(*) as partner_count
                FROM res_partner 
                WHERE active = true
                GROUP BY is_company
            """
            request.env.cr.execute(partners_query)
            partners_data = request.env.cr.dictfetchall()
            
            # 12. Datos para rangos de precio
            price_ranges_query = """
                SELECT 
                    CASE 
                        WHEN list_price < 100 THEN '0-100'
                        WHEN list_price < 500 THEN '100-500'
                        WHEN list_price < 1000 THEN '500-1000'
                        ELSE '1000+' 
                    END as price_range,
                    COUNT(*) as product_count
                FROM product_template
                WHERE sale_ok = true AND list_price > 0
                GROUP BY 
                    CASE 
                        WHEN list_price < 100 THEN '0-100'
                        WHEN list_price < 500 THEN '100-500' 
                        WHEN list_price < 1000 THEN '500-1000'
                        ELSE '1000+'
                    END
                ORDER BY 
                    CASE 
                        WHEN list_price < 100 THEN 1
                        WHEN list_price < 500 THEN 2
                        WHEN list_price < 1000 THEN 3
                        ELSE 4
                    END
            """
            request.env.cr.execute(price_ranges_query)
            price_ranges = request.env.cr.dictfetchall()
            
            # 13. Retornar todos los datos
            return {
                'status': 'success',
                'data': {
                    'categories': categories,
                    'partners': partners_data,
                    'price_ranges': price_ranges
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
</div>

---

# Paso 6: Crear Templates XML

## 6.1 ¿Qué son los templates?

<div class="info">
Los <strong>templates</strong> definen cómo se ve la interfaz. Es como el HTML pero con superpoderes de Odoo.
</div>

## 6.2 Template principal

<div class="code">
<!-- Crear archivo: static/src/xml/main_dashboard_template.xml -->
<templates xml:space="preserve">

    <!-- Template Principal del Dashboard -->
    <t t-name="owl_practica_new.MainDashboard" owl="1">
        <div class="p-4 dashboard-main-container">
            <!-- Título -->
            <h2>Dashboard - Datos de la Base de Datos</h2>
            
            <!-- Componente de Controles Básicos -->
            <BasicControlsWidget />
            
            <!-- Componente de Datos de Base de Datos -->
            <DatabaseDataWidget />
            
            <!-- Componente de Análisis de Datos -->
            <AnalyticsWidget />
            
            <!-- Mensaje de éxito -->
            <div class="mt-4 alert alert-info">
                <i class="fa fa-info-circle"/> 
                <strong>¡Datos en tiempo real!</strong> Tutorial completado exitosamente.
                <br/>
                <small class="text-muted">Ahora dominas los fundamentos de OWL.</small>
            </div>
        </div>
    </t>

</templates>
</code>

<div class="success">
<strong>💡 Concepto clave:</strong> <code>owl="1"</code> le dice a Odoo que este es un template OWL. Los nombres de componentes en el template deben coincidir con los registrados en <code>static components</code>.
</div>

---

# Paso 6.2: Template de Controles Básicos

<div class="code">
<!-- Crear archivo: static/src/xml/basic_controls_template.xml -->
<templates xml:space="preserve">

    <t t-name="owl_practica_new.BasicControls" owl="1">
        <div class="card mb-4">
            <div class="card-header">
                <h4><i class="fa fa-gamepad"/> Controles Básicos - Estado Reactivo</h4>
            </div>
            <div class="card-body">
                <!-- Mostrar estado actual -->
                <div class="row mb-3">
                    <div class="col-md-6">
                        <div class="alert alert-primary">
                            <strong>Contador:</strong> <span t-esc="state.count"/>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="alert alert-secondary">
                            <strong>Mensaje:</strong> <span t-esc="state.message"/>
                        </div>
                    </div>
                </div>
                
                <!-- Botones interactivos -->
                <div class="btn-group">
                    <button class="btn btn-primary" t-on-click="increment">
                        <i class="fa fa-plus"/> Incrementar
                    </button>
                    <button class="btn btn-info" t-on-click="changeMessage">
                        <i class="fa fa-edit"/> Cambiar Mensaje
                    </button>
                </div>
                
                <!-- Explicación -->
                <div class="mt-3">
                    <small class="text-muted">
                        <i class="fa fa-lightbulb-o"/> 
                        Los cambios en el estado se reflejan automáticamente en la interfaz
                    </small>
                </div>
            </div>
        </div>
    </t>

</templates>
</code>

<div class="warning">
<strong>⚠️ Sintaxis importante:</strong>
<br>• <code>t-esc="variable"</code> - Muestra el valor de una variable
<br>• <code>t-on-click="metodo"</code> - Ejecuta un método al hacer clic
<br>• <code>state.propiedad</code> - Accede a propiedades del estado
</div>

---

# Paso 6.3: Template de Datos de BD

<div class="code">
<!-- Crear archivo: static/src/xml/database_data_template.xml -->
<templates xml:space="preserve">

    <t t-name="owl_practica_new.DatabaseData" owl="1">
        <div class="card mb-4">
            <div class="card-header">
                <h4><i class="fa fa-database"/> Datos de Base de Datos</h4>
            </div>
            <div class="card-body">
                
                <!-- Indicador de carga -->
                <div t-if="state.loading" class="text-center">
                    <i class="fa fa-spinner fa-spin fa-2x"/>
                    <p>Cargando datos...</p>
                </div>
                
                <!-- Pestañas -->
                <div t-if="!state.loading">
                    <ul class="nav nav-tabs mb-3">
                        <li class="nav-item">
                            <a class="nav-link" 
                               t-att-class="state.activeTab === 'partners' ? 'active' : ''"
                               href="#" t-on-click="() => this.switchTab('partners')">
                                <i class="fa fa-users"/> Contactos (<t t-esc="state.partners.length"/>)
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link"
                               t-att-class="state.activeTab === 'products' ? 'active' : ''"
                               href="#" t-on-click="() => this.switchTab('products')">
                                <i class="fa fa-cube"/> Productos (<t t-esc="state.products.length"/>)
                            </a>
                        </li>
                    </ul>
                    
                    <!-- Contenido de pestañas -->
                    <div t-if="state.activeTab === 'partners'">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>Nombre</th>
                                        <th>Email</th>
                                        <th>Teléfono</th>
                                        <th>Tipo</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr t-foreach="state.partners.slice(0, 10)" t-as="partner" t-key="partner.id">
                                        <td><t t-esc="partner.name"/></td>
                                        <td><t t-esc="partner.email || 'Sin email'"/></td>
                                        <td><t t-esc="partner.phone || 'Sin teléfono'"/></td>
                                        <td>
                                            <span t-if="partner.is_company" class="badge badge-primary">Empresa</span>
                                            <span t-else="" class="badge badge-secondary">Persona</span>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
</div>
</code>

---

# Resumen del Manual (Final)

## 🎯 **Archivos completados:**

✅ **13 archivos** creados paso a paso  
✅ **Componentes OWL** con estado reactivo  
✅ **Controladores HTTP** para API backend  
✅ **Templates XML** para interfaz  
✅ **Integración completa** frontend-backend  

## 📚 **Conceptos aprendidos:**

- **useState** - Estado reactivo automático
- **onWillStart** - Hook de ciclo de vida  
- **Promise.all** - Peticiones paralelas
- **JSON-RPC** - Protocolo de Odoo
- **Chart.js** - Gráficos interactivos
- **QWeb templates** - Sistema de plantillas

## 🚀 **Siguientes pasos:**

1. **Instalar el módulo** en tu instancia Odoo
2. **Probar funcionalidades** paso a paso
3. **Experimentar con modificaciones**
4. **Crear tus propios componentes**

---

# ¡Felicitaciones! 🎉

**Has completado el manual de desarrollo OWL**

Tu dashboard interactivo está listo con:
- ✅ Controles reactivos
- ✅ Datos en tiempo real  
- ✅ Gráficos dinámicos
- ✅ Arquitectura escalable

**¡Ahora eres un desarrollador OWL!** 🚀
