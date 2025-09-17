# 🦉 Ejemplos de Código OWL - Estate Dashboard

## 📋 **Índice de Ejemplos**
1. [Componente Base](#componente-base)
2. [Estado Reactivo](#estado-reactivo)
3. [Hooks del Ciclo de Vida](#hooks-del-ciclo-de-vida)
4. [Directivas de Template](#directivas-de-template)
5. [Event Handling](#event-handling)
6. [Integración Chart.js](#integración-chartjs)

---

## 🧩 **1. Componente Base**

### **Importaciones OWL**
```javascript
import { Component, useState, onWillStart } from "@odoo/owl";
```

### **Declaración del Componente**
```javascript
export class EstateOwlWidget extends Component {
    static template = "estate_owl.EstateWidget";
    
    setup() {
        // Configuración del componente
    }
}
```

### **Conexión Template**
```xml
<t t-name="estate_owl.EstateWidget" owl="1">
    <!-- Template content -->
</t>
```

---

## 📊 **2. Estado Reactivo**

### **Definición del Estado**
```javascript
setup() {
    this.state = useState({ 
        properties: [],           // Array reactivo
        offers: [],              
        propertyTypes: [],       
        dashboardData: null,     // Objeto reactivo
        loading: true,           // Boolean reactivo
        activeTab: 'properties', // String reactivo
        activeChart: 'states'    
    });
}
```

### **Actualización Reactiva**
```javascript
// ✅ Correcto - OWL detecta el cambio
this.state.loading = false;
this.state.activeTab = 'offers';
this.state.properties.push(newProperty);

// ❌ Incorrecto - No es reactivo
this.properties = [];
this.loading = false;
```

---

## ⏰ **3. Hooks del Ciclo de Vida**

### **onWillStart - Carga Inicial**
```javascript
setup() {
    onWillStart(async () => {
        console.log("🚀 Componente iniciando...");
        await this.loadData();
        console.log("✅ Datos cargados");
    });
}
```

### **Método de Carga de Datos**
```javascript
async loadData() {
    try {
        this.state.loading = true;
        
        // Llamadas paralelas a la API
        const [propertiesData, offersData, typesData, dashboardData] = 
            await Promise.all([
                this.fetchProperties(),
                this.fetchOffers(),
                this.fetchPropertyTypes(),
                this.fetchDashboardData()
            ]);
        
        // Actualización reactiva del estado
        this.state.properties = propertiesData.result?.data || [];
        this.state.offers = offersData.result?.data || [];
        this.state.propertyTypes = typesData.result?.data || [];
        this.state.dashboardData = dashboardData.result?.data || null;
        this.state.loading = false;
        
        // Crear gráficas después del renderizado
        setTimeout(() => this.createCharts(), 500);
        
    } catch (error) {
        console.error("Error loading data:", error);
        this.state.loading = false;
    }
}
```

---

## 🎨 **4. Directivas de Template**

### **t-if / t-else - Renderizado Condicional**
```xml
<!-- Loading Spinner -->
<div t-if="state.loading" class="estate-loading">
    <div class="spinner-border" role="status">
        <span class="visually-hidden">Cargando...</span>
    </div>
    <p class="mt-3">Cargando datos de propiedades...</p>
</div>

<!-- Contenido Principal -->
<div t-else="" class="estate-content">
    <!-- Dashboard content -->
</div>
```

### **t-foreach - Iteración de Listas**
```xml
<!-- Tabla de Propiedades -->
<tbody>
    <tr t-foreach="state.properties" t-as="property" t-key="property.id">
        <td>
            <strong t-esc="property.name"/>
            <br/>
            <small class="text-muted" t-esc="property.description"/>
        </td>
        <td t-esc="property.postcode"/>
        <td>
            <span class="badge bg-info">
                <t t-esc="formatCurrency(property.expected_price)"/>
            </span>
        </td>
        <td>
            <span t-if="property.selling_price" class="badge bg-success">
                <t t-esc="formatCurrency(property.selling_price)"/>
            </span>
            <span t-else="" class="text-muted">No vendida</span>
        </td>
    </tr>
</tbody>
```

### **t-esc - Interpolación de Datos**
```xml
<!-- Contadores Dinámicos -->
<div class="estate-stat-item">
    <span class="estate-stat-number" t-esc="state.properties.length"/>
    <small class="estate-stat-label">Propiedades</small>
</div>

<!-- Datos Formateados -->
<td t-esc="formatCurrency(property.expected_price)"/>
<td t-esc="formatDate(property.date_availability)"/>
```

### **t-attf-class - Clases Dinámicas**
```xml
<!-- Pestañas Activas -->
<button t-attf-class="nav-link #{state.activeTab === 'properties' ? 'active' : ''}"
        type="button" role="tab">
    <i class="fa fa-building me-1"/>
    Propiedades (<t t-esc="state.properties.length"/>)
</button>

<!-- Estados de Propiedades -->
<span t-attf-class="badge #{property.state === 'sold' ? 'bg-success' : 
                           property.state === 'new' ? 'bg-primary' : 
                           property.state === 'canceled' ? 'bg-danger' : 'bg-warning'}">
    <t t-esc="property.state"/>
</span>
```

---

## 🖱️ **5. Event Handling**

### **t-on-click - Manejo de Clicks**
```xml
<!-- Navegación de Pestañas -->
<button t-on-click="() => this.switchTab('properties')">
    <i class="fa fa-building me-1"/>
    Propiedades
</button>

<button t-on-click="() => this.switchTab('offers')">
    <i class="fa fa-money me-1"/>
    Ofertas
</button>

<!-- Cambio de Gráficas -->
<button t-on-click="() => this.switchChart('states')"
        class="btn btn-outline-primary">
    Estados
</button>
```

### **Métodos de Event Handling**
```javascript
switchTab(tabName) {
    console.log("Switching to tab:", tabName);
    this.state.activeTab = tabName;
    // OWL automáticamente re-renderiza la UI
}

switchChart(chartName) {
    console.log("Switching to chart:", chartName);
    this.state.activeChart = chartName;
    
    // Recrear gráfica después del cambio
    setTimeout(() => {
        this.createCharts();
    }, 200);
}
```

---

## 📊 **6. Integración Chart.js**

### **Método para Crear Gráficas**
```javascript
createCharts() {
    console.log("Creating chart for:", this.state.activeChart);
    
    if (!this.state.dashboardData) {
        console.error("No dashboard data available");
        return;
    }
    
    // Limpiar gráfico anterior
    if (window.estateChart && typeof window.estateChart.destroy === 'function') {
        window.estateChart.destroy();
    }
    
    const canvas = document.getElementById('estateChart');
    if (!canvas) {
        console.error("Canvas element not found");
        return;
    }
    
    const ctx = canvas.getContext('2d');
    let chartConfig = this.getChartConfig();
    
    // Crear nueva instancia de Chart.js
    window.estateChart = new Chart(ctx, chartConfig);
}
```

### **Configuraciones de Gráficas**
```javascript
getChartConfig() {
    const { activeChart, dashboardData } = this.state;
    
    switch (activeChart) {
        case 'states':
            return {
                type: 'doughnut',
                data: {
                    labels: dashboardData.properties_by_state.map(s => s.state_name),
                    datasets: [{
                        label: 'Propiedades por Estado',
                        data: dashboardData.properties_by_state.map(s => s.property_count),
                        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'],
                        borderColor: '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Propiedades por Estado'
                        }
                    }
                }
            };
            
        case 'types':
            return {
                type: 'bar',
                data: {
                    labels: dashboardData.properties_by_type.map(t => t.type_name),
                    datasets: [{
                        label: 'Propiedades por Tipo',
                        data: dashboardData.properties_by_type.map(t => t.property_count),
                        backgroundColor: '#36A2EB',
                        borderColor: '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Propiedades por Tipo'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            };
            
        // Más configuraciones...
        default:
            return {};
    }
}
```

---

## 🔧 **7. Métodos Utilitarios**

### **Formateo de Datos**
```javascript
formatCurrency(amount) {
    if (!amount) return '$0';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

formatDate(dateString) {
    if (!dateString) return 'No disponible';
    return new Date(dateString).toLocaleDateString('es-ES');
}
```

### **Llamadas a la API**
```javascript
async fetchProperties() {
    return await fetch('/estate/get_properties', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: {},
            id: Math.floor(Math.random() * 1000000)
        })
    }).then(response => response.json());
}
```

---

## 🎯 **8. Casos de Uso Completos**

### **Escenario: Cambiar de Pestaña**
```
1. Usuario hace clic en "Ofertas"
   ↓
2. t-on-click="() => this.switchTab('offers')"
   ↓
3. switchTab('offers') ejecuta this.state.activeTab = 'offers'
   ↓
4. OWL detecta cambio en state.activeTab
   ↓
5. Re-evalúa t-attf-class="nav-link #{state.activeTab === 'offers' ? 'active' : ''}"
   ↓
6. Actualiza DOM: clase 'active' se mueve a pestaña Ofertas
   ↓
7. CSS aplica estilos de pestaña activa
```

### **Escenario: Carga de Datos**
```
1. Componente se monta
   ↓
2. setup() se ejecuta
   ↓
3. onWillStart() se ejecuta
   ↓
4. loadData() se ejecuta
   ↓
5. this.state.loading = true → Spinner visible
   ↓
6. Fetch de datos desde backend
   ↓
7. this.state.properties = data → Tabla se llena
   ↓
8. this.state.loading = false → Spinner oculto, contenido visible
```

---

## 📊 **9. Estructura de Archivos**

### **Organización del Proyecto**
```
estate_owl/
├── __manifest__.py
├── controllers/
│   └── controllers.py
├── static/src/
│   ├── js/
│   │   └── estate_widget.js      # ← Componente OWL
│   ├── xml/
│   │   └── estate_widget.xml     # ← Template OWL
│   └── css/
│       └── estate_widget.css     # ← Estilos
└── views/
    ├── estate_action.xml
    └── estate_menu.xml
```

### **Assets en Manifest**
```python
"assets": {
    "web.assets_backend": [
        "https://cdn.jsdelivr.net/npm/chart.js",
        "estate_owl/static/src/css/estate_widget.css",
        "estate_owl/static/src/js/estate_widget.js",
        "estate_owl/static/src/xml/estate_widget.xml",
    ],
}
```

---

## 🧪 **10. Testing y Debugging**

### **Console Logs para Debug**
```javascript
setup() {
    console.log("EstateOwlWidget setup called");
    // ...
}

switchTab(tabName) {
    console.log("Switching to tab:", tabName);
    // ...
}

async loadData() {
    console.log("Loading estate data...");
    // ...
    console.log("Estate data loaded:", {
        properties: this.state.properties.length,
        offers: this.state.offers.length
    });
}
```

### **Error Handling**
```javascript
async loadData() {
    try {
        // Código de carga
    } catch (error) {
        console.error("Error loading estate data:", error);
        this.state.loading = false;
        // Mostrar mensaje de error al usuario
    }
}
```

---

## 🎯 **11. Best Practices Implementadas**

### **✅ Estado Reactivo**
- Usar `useState()` para todos los datos que afectan la UI
- No modificar directamente arrays/objetos fuera del state
- Mantener el estado lo más plano posible

### **✅ Performance**
- Usar `t-key` en `t-foreach` para optimizar re-renders
- `setTimeout()` para operaciones post-render (gráficas)
- Limpiar recursos (Chart.js destroy)

### **✅ Mantenibilidad**
- Separar lógica en métodos específicos
- Nombres descriptivos para métodos y variables
- Comentarios en código complejo

### **✅ UX**
- Loading states para feedback visual
- Manejo de errores graceful
- Transiciones suaves con CSS

---

## 🚀 **Conclusión**

Este proyecto demuestra un **uso completo y profesional** de OWL en Odoo, implementando:

- ✅ **Todos los conceptos fundamentales** de OWL
- ✅ **Integración con librerías externas** (Chart.js)
- ✅ **UI moderna y responsiva**
- ✅ **Arquitectura escalable y mantenible**
- ✅ **Best practices** de desarrollo frontend

**¡Un dashboard completo construido con la potencia de OWL! 🦉🚀**
