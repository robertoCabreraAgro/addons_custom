import { Component, useState, onWillStart } from "@odoo/owl";

console.log("Loading estate_widget.js");

export class EstateOwlWidget extends Component {
    static template = "estate_owl.EstateWidget";
    
    setup() {
        console.log("EstateOwlWidget setup called");
        this.state = useState({ 
            properties: [],
            offers: [],
            propertyTypes: [],
            dashboardData: null,
            loading: true,
            activeTab: 'properties',
            activeChart: 'states'
        });
        
        onWillStart(async () => {
            await this.loadData();
        });
    }
    
    async loadData() {
        try {
            console.log("Loading estate data...");
            
            // Cargar propiedades
            const propertiesResponse = await fetch('/estate/get_properties', {
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
            });
            const propertiesData = await propertiesResponse.json();
            
            // Cargar ofertas
            const offersResponse = await fetch('/estate/get_offers', {
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
            });
            const offersData = await offersResponse.json();
            
            // Cargar tipos de propiedades
            const typesResponse = await fetch('/estate/get_property_types', {
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
            });
            const typesData = await typesResponse.json();
            
            // Cargar datos del dashboard
            const dashboardResponse = await fetch('/estate/get_dashboard_data', {
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
            });
            const dashboardData = await dashboardResponse.json();
            
            this.state.properties = propertiesData.result?.data || [];
            this.state.offers = offersData.result?.data || [];
            this.state.propertyTypes = typesData.result?.data || [];
            this.state.dashboardData = dashboardData.result?.data || null;
            this.state.loading = false;
            
            console.log("Estate data loaded:", {
                properties: this.state.properties.length,
                offers: this.state.offers.length,
                propertyTypes: this.state.propertyTypes.length,
                dashboardData: this.state.dashboardData
            });
            
            // Crear gráficos después de que se rendericen los elementos
            setTimeout(() => {
                this.createCharts();
            }, 500);
            
        } catch (error) {
            console.error("Error loading estate data:", error);
            this.state.loading = false;
        }
    }
    
    switchTab(tabName) {
        console.log("Switching to tab:", tabName);
        this.state.activeTab = tabName;
    }
    
    switchChart(chartName) {
        console.log("Switching to chart:", chartName);
        this.state.activeChart = chartName;
        setTimeout(() => {
            this.createCharts();
        }, 200);
    }
    
    createCharts() {
        console.log("createCharts called with activeChart:", this.state.activeChart);
        console.log("dashboardData:", this.state.dashboardData);
        
        if (!this.state.dashboardData) {
            console.error("No dashboard data available");
            return;
        }
        
        // Limpiar gráficos existentes
        if (window.estateChart && typeof window.estateChart.destroy === 'function') {
            window.estateChart.destroy();
        }
        
        const canvas = document.getElementById('estateChart');
        if (!canvas) {
            console.error("Canvas element not found");
            return;
        }
        
        console.log("Canvas found, creating chart...");
        const ctx = canvas.getContext('2d');
        
        let chartConfig = {};
        
        if (this.state.activeChart === 'states') {
            console.log("Properties by state data:", this.state.dashboardData.properties_by_state);
            chartConfig = {
                type: 'doughnut',
                data: {
                    labels: this.state.dashboardData.properties_by_state.map(s => s.state_name),
                    datasets: [{
                        label: 'Propiedades por Estado',
                        data: this.state.dashboardData.properties_by_state.map(s => s.property_count),
                        backgroundColor: [
                            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
                        ],
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
        } else if (this.state.activeChart === 'types') {
            console.log("Properties by type data:", this.state.dashboardData.properties_by_type);
            chartConfig = {
                type: 'bar',
                data: {
                    labels: this.state.dashboardData.properties_by_type.map(t => t.type_name),
                    datasets: [{
                        label: 'Propiedades por Tipo',
                        data: this.state.dashboardData.properties_by_type.map(t => t.property_count),
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
        } else if (this.state.activeChart === 'prices') {
            console.log("Price ranges data:", this.state.dashboardData.price_ranges);
            chartConfig = {
                type: 'bar',
                data: {
                    labels: this.state.dashboardData.price_ranges.map(p => p.price_range),
                    datasets: [{
                        label: 'Propiedades por Rango de Precio',
                        data: this.state.dashboardData.price_ranges.map(p => p.property_count),
                        backgroundColor: '#4BC0C0',
                        borderColor: '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Propiedades por Rango de Precio'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            };
        } else if (this.state.activeChart === 'offers') {
            console.log("Offers by status data:", this.state.dashboardData.offers_by_status);
            chartConfig = {
                type: 'pie',
                data: {
                    labels: this.state.dashboardData.offers_by_status.map(o => o.status_name),
                    datasets: [{
                        label: 'Ofertas por Estado',
                        data: this.state.dashboardData.offers_by_status.map(o => o.offer_count),
                        backgroundColor: ['#FF9F40', '#FF6384', '#FFCE56'],
                        borderColor: '#ffffff',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Ofertas por Estado'
                        }
                    }
                }
            };
        }
        
        if (window.Chart && typeof window.Chart === 'function') {
            console.log("Creating Chart.js chart...");
            window.estateChart = new Chart(ctx, chartConfig);
        } else {
            console.error("Chart.js not loaded");
        }
    }
    
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
}
