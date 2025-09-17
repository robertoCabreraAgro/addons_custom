---
theme: "white"
title: "OWL en Estate Dashboard"
author: "JEM - Tutorial Odoo"
date: "Septiembre 2025"
---

# 🦉 **OWL en mi Práctica Estate Dashboard**
### *Odoo Web Library - Componentes Reactivos*

---

## 📋 **Agenda de la Presentación**

1. **¿Qué es OWL?**
2. **Elementos OWL Implementados**
3. **Estructura del Componente**
4. **Hooks del Ciclo de Vida**
5. **Manejo de Estado Reactivo**
6. **Template y Directivas**
7. **Event Handling**
8. **Demo en Vivo**
9. **Conclusiones**

---

## 🤔 **¿Qué es OWL?**

### **Odoo Web Library (OWL)**
- Framework frontend **reactivo** de Odoo 18+
- Basado en **componentes** reutilizables
- Manejo de **estado reactivo** automático
- Sistema de **templates** con directivas
- **Hooks** para ciclo de vida de componentes

### **¿Por qué OWL?**
- ✅ **Performance** mejorada
- ✅ **Reactividad** automática
- ✅ **Desarrollo** más intuitivo
- ✅ **Mantenimiento** simplificado

---

## 🏗️ **Arquitectura de mi Estate Dashboard**

```
Estate OWL Widget
├── 📁 JavaScript Component (estate_widget.js)
├── 📁 XML Template (estate_widget.xml)  
├── 📁 CSS Styles (estate_widget.css)
└── 📁 Python Controller (controllers.py)
```

### **Flujo de Datos:**
```
Backend (Python) → API Endpoints → Frontend (OWL) → UI Reactiva
```

---

## 🧩 **1. Estructura del Componente OWL**

### **Clase Principal**
```javascript
import { Component, useState, onWillStart } from "@odoo/owl";

export class EstateOwlWidget extends Component {
    static template = "estate_owl.EstateWidget";
    
    setup() {
        // Configuración del componente
    }
}
```

### **Elementos Clave:**
- ✅ **Component**: Clase base de OWL
- ✅ **Template estático**: Conexión con XML
- ✅ **Setup()**: Método de inicialización

---

## 🔄 **2. Hooks del Ciclo de Vida**

### **onWillStart - Carga Inicial**
```javascript
setup() {
    onWillStart(async () => {
        await this.loadData();
    });
}
```

### **¿Qué hace?**
- 🚀 Se ejecuta **antes** del primer renderizado
- 📊 Carga datos desde el **backend**
- ⏱️ **Asíncrono** - no bloquea la UI

### **Flujo de Ejecución:**
```
Component Mount → onWillStart → loadData() → Render Template
```

---

## 📊 **3. Estado Reactivo con useState**

### **Definición del Estado**
```javascript
this.state = useState({ 
    properties: [],           // Lista de propiedades
    offers: [],              // Lista de ofertas
    propertyTypes: [],       // Tipos de propiedades
    dashboardData: null,     // Datos para gráficas
    loading: true,           // Estado de carga
    activeTab: 'properties', // Pestaña activa
    activeChart: 'states'    // Gráfica activa
});
```

### **🎯 Reactividad Automática**
- Cuando `this.state.loading = false` → UI se actualiza automáticamente
- Cuando `this.state.activeTab = 'offers'` → Cambia pestaña sin refresh
- Cuando `this.state.properties.length` cambia → Contador se actualiza

---

## 🎨 **4. Template XML y Directivas OWL**

### **Estructura del Template**
```xml
<t t-name="estate_owl.EstateWidget" owl="1">
    <div class="estate-owl-container">
        <!-- Contenido reactivo -->
    </div>
</t>
```

### **Directivas Implementadas:**

#### **📌 t-if / t-else (Renderizado Condicional)**
```xml
<div t-if="state.loading" class="estate-loading">
    <div class="spinner-border">Cargando...</div>
</div>
<div t-else="" class="estate-content">
    <!-- Contenido principal -->
</div>
```

---

## 🔄 **5. Directivas de Iteración**

### **t-foreach - Renderizar Listas**
```xml
<tr t-foreach="state.properties" t-as="property" t-key="property.id">
    <td t-esc="property.name"/>
    <td t-esc="property.postcode"/>
    <td t-esc="formatCurrency(property.expected_price)"/>
</tr>
```

### **¿Cómo funciona?**
- 🔁 **Itera** sobre `state.properties`
- 🏷️ **Cada elemento** se llama `property`
- 🔑 **Key único** para performance
- 🔄 **Se actualiza automáticamente** cuando cambia el array

---

## 💫 **6. Interpolación de Datos**

### **t-esc - Mostrar Datos**
```xml
<span class="estate-stat-number" t-esc="state.properties.length"/>
<span t-esc="property.name"/>
<span t-esc="formatCurrency(property.expected_price)"/>
```

### **t-attf-class - Clases Dinámicas**
```xml
<button t-attf-class="nav-link #{state.activeTab === 'properties' ? 'active' : ''}">
<span t-attf-class="badge #{property.state === 'sold' ? 'bg-success' : 'bg-warning'}">
```

### **Resultado:**
- Clases CSS que **cambian dinámicamente**
- Estilos **basados en el estado**

---

## 🖱️ **7. Event Handling**

### **t-on-click - Manejo de Eventos**
```xml
<button t-on-click="() => this.switchTab('properties')">
    Propiedades
</button>
<button t-on-click="() => this.switchChart('states')">
    Gráfico Estados
</button>
```

### **Métodos del Componente:**
```javascript
switchTab(tabName) {
    this.state.activeTab = tabName; // ¡Reactividad automática!
}

switchChart(chartName) {
    this.state.activeChart = chartName;
    setTimeout(() => this.createCharts(), 200);
}
```

---

## 📊 **8. Integración con Chart.js**

### **Gráficas Dinámicas**
```javascript
createCharts() {
    if (!this.state.dashboardData) return;
    
    // Limpiar gráfico anterior
    if (window.estateChart) {
        window.estateChart.destroy();
    }
    
    // Crear nuevo gráfico basado en estado
    const canvas = document.getElementById('estateChart');
    const ctx = canvas.getContext('2d');
    
    let chartConfig = {};
    if (this.state.activeChart === 'states') {
        chartConfig = { /* Configuración doughnut */ };
    } else if (this.state.activeChart === 'types') {
        chartConfig = { /* Configuración bar */ };
    }
    
    window.estateChart = new Chart(ctx, chartConfig);
}
```

---

## 🔄 **9. Flujo Completo de Reactividad**

### **Ejemplo: Cambiar Pestaña**
```
1. Usuario hace clic → t-on-click="() => this.switchTab('offers')"
2. Método switchTab() → this.state.activeTab = 'offers'
3. OWL detecta cambio → Re-evalúa template
4. UI se actualiza → Nueva pestaña activa, sin refresh
```

### **Ejemplo: Mostrar/Ocultar Loading**
```
1. loadData() inicia → this.state.loading = true
2. OWL renderiza → Spinner visible, contenido oculto
3. Datos cargados → this.state.loading = false  
4. OWL re-renderiza → Spinner oculto, contenido visible
```

---

## 📁 **10. Estructura de Archivos OWL**

### **JavaScript (Lógica)**
```javascript
// estate_widget.js
export class EstateOwlWidget extends Component {
    static template = "estate_owl.EstateWidget";
    // Lógica del componente
}
```

### **XML (Template)**
```xml
<!-- estate_widget.xml -->
<t t-name="estate_owl.EstateWidget" owl="1">
    <!-- Template reactivo -->
</t>
```

### **Manifest (Configuración)**
```python
# __manifest__.py
"assets": {
    "web.assets_backend": [
        "estate_owl/static/src/js/estate_widget.js",
        "estate_owl/static/src/xml/estate_widget.xml",
        "estate_owl/static/src/css/estate_widget.css",
    ],
}
```

---

## 🎯 **11. Funcionalidades Implementadas**

### **📊 Dashboard Interactivo**
- ✅ **4 pestañas** navegables
- ✅ **Tablas dinámicas** con datos de BD
- ✅ **Gráficas interactivas** (Chart.js)
- ✅ **Contadores** en tiempo real

### **🔄 Gestión de Estado**
- ✅ **Loading states** con spinners
- ✅ **Cambio de pestañas** sin refresh
- ✅ **Gráficas alternables**
- ✅ **Formateo** de moneda y fechas

### **🎨 UI/UX Moderna**
- ✅ **Diseño responsivo**
- ✅ **Animaciones CSS**
- ✅ **Estados visuales** claros
- ✅ **Iconografía** Font Awesome

---

## 📈 **12. Ventajas de usar OWL**

### **vs Vanilla JavaScript:**
- ❌ **Sin OWL**: Manipulación manual del DOM
- ✅ **Con OWL**: Reactividad automática

### **vs jQuery/Legacy:**
- ❌ **Sin OWL**: `$('#element').html(newContent)`
- ✅ **Con OWL**: `this.state.content = newContent`

### **Beneficios Reales:**
- 🚀 **Menos código** para la misma funcionalidad
- 🐛 **Menos bugs** por manipulación manual
- 🧪 **Más testeable** y mantenible
- ⚡ **Performance** optimizada

---

## 🧪 **13. Demo en Vivo**

### **Lo que veremos:**
1. **Carga inicial** con loading spinner
2. **Navegación entre pestañas** (Propiedades → Ofertas → Tipos → Gráficas)
3. **Gráficas interactivas** (Estados → Tipos → Precios → Ofertas)
4. **Datos reactivos** en contadores
5. **Estados condicionales** en tablas

### **Elementos OWL en acción:**
- 🔄 **useState** actualizando contadores
- 🎨 **t-if/t-else** mostrando/ocultando contenido
- 🔁 **t-foreach** renderizando filas de tablas
- 🖱️ **t-on-click** manejando navegación
- 💫 **t-attf-class** cambiando estilos dinámicamente

---

## 📊 **14. Métricas de Implementación**

### **Líneas de Código:**
- 📄 **JavaScript**: ~280 líneas
- 📄 **XML Template**: ~300 líneas  
- 📄 **CSS**: ~600 líneas
- 📄 **Python**: ~170 líneas

### **Elementos OWL Utilizados:**
- 🧩 **1 Componente** principal
- 🔄 **2 Hooks** (useState, onWillStart)
- 🎨 **8 Directivas** diferentes
- 🖱️ **10+ Event handlers**
- 📊 **7 Variables** de estado reactivo

---

## 🎓 **15. Conceptos OWL Dominados**

### **✅ Nivel Básico:**
- Componentes y templates
- Estado reactivo básico
- Renderizado condicional
- Event handling simple

### **✅ Nivel Intermedio:**
- Hooks del ciclo de vida
- Iteración de listas
- Interpolación de datos
- Clases dinámicas

### **✅ Nivel Avanzado:**
- Integración con librerías externas (Chart.js)
- Formateo de datos personalizado
- Manejo de estados complejos
- Optimización de performance

---

## 🔍 **16. Análisis Técnico**

### **Patrón de Diseño:**
```
MVVM (Model-View-ViewModel)
├── Model: Python Controllers + Odoo Models
├── View: XML Templates + CSS
└── ViewModel: OWL Component (estate_widget.js)
```

### **Flujo de Datos:**
```
User Interaction → Event Handler → State Change → Template Re-render → DOM Update
```

### **Arquitectura:**
- 🏗️ **Separación de responsabilidades**
- 🔄 **Flujo unidireccional de datos**
- 🧩 **Componentes reutilizables**

---

## 🚀 **17. Próximos Pasos**

### **Funcionalidades a Agregar:**
- 🔄 **Auto-refresh** con WebSockets
- 📱 **PWA** (Progressive Web App)
- 🌙 **Dark mode** toggle
- 📊 **Más tipos de gráficas**
- 🔍 **Filtros** y búsqueda
- 📤 **Export** a PDF/Excel

### **Mejoras Técnicas:**
- ⚡ **Lazy loading** de datos
- 🧪 **Tests** unitarios
- 📦 **Bundle optimization**
- 🔐 **Security enhancements**

---

## 🎯 **18. Conclusiones**

### **¿Qué logré con OWL?**
- ✅ **Dashboard completo** y funcional
- ✅ **UI reactiva** e intuitiva
- ✅ **Código mantenible** y escalable
- ✅ **Experiencia moderna** para usuarios

### **Lecciones Aprendidas:**
- 🎓 OWL **simplifica** el desarrollo frontend
- 🔄 La **reactividad** mejora UX significativamente
- 🧩 Los **componentes** facilitan reutilización
- 📊 **Integración** con librerías es sencilla

### **Valor del Proyecto:**
- 💼 **Portfolio** de habilidades Odoo modernas
- 🛠️ **Base** para proyectos futuros
- 📚 **Conocimiento** aplicable a otros frameworks
- 🚀 **Preparación** para Odoo 18+

---

## 🙏 **¡Gracias por su Atención!**

### **Preguntas y Respuestas**

¿Dudas sobre algún elemento específico de OWL?

### **Enlaces Útiles:**
- 📖 **Documentación OWL**: [github.com/odoo/owl](https://github.com/odoo/owl)
- 🎓 **Tutorial Odoo**: Mis apuntes y prácticas
- 💻 **Código fuente**: `estate_owl` module

---

### **Contacto:**
- 👨‍💻 **Desarrollador**: JEM
- 📧 **Email**: [tu-email@ejemplo.com]
- 🐙 **GitHub**: [tu-usuario]
- 💼 **LinkedIn**: [tu-perfil]

**¡Estate OWL Dashboard - Powered by OWL! 🦉🏠**
