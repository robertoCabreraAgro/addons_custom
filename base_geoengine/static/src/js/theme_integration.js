/** @odoo-module **/

/**
 * GeoEngine Theme Integration
 * 
 * Simple integration with Odoo's native dark mode system.
 * Ensures GeoEngine components properly inherit theme styling.
 */

// Initialize theme integration when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeGeoEngineTheme();
});

/**
 * Initialize GeoEngine theme integration
 */
function initializeGeoEngineTheme() {
    // Apply theme-aware classes to existing GeoEngine elements
    applyThemeClasses();
    
    // Set up observer for dynamically added elements
    setupElementObserver();
    
    // Listen for Odoo theme changes (if supported)
    setupThemeChangeListener();
}

/**
 * Apply theme-aware classes to GeoEngine elements
 */
function applyThemeClasses() {
    const geoElements = document.querySelectorAll(
        '.geoengine-view, .geoengine-map-container, .geoengine-controls, .geoengine-layer-panel'
    );
    
    geoElements.forEach(element => {
        // Add theme-aware class if not already present
        if (!element.classList.contains('geoengine-themed')) {
            element.classList.add('geoengine-themed');
        }
        
        // Ensure proper Bootstrap theme inheritance
        if (!element.getAttribute('data-bs-theme')) {
            const bodyTheme = document.body.getAttribute('data-bs-theme') || 
                             document.documentElement.getAttribute('data-bs-theme');
            if (bodyTheme) {
                element.setAttribute('data-bs-theme', bodyTheme);
            }
        }
    });
}

/**
 * Set up MutationObserver for dynamically added GeoEngine elements
 */
function setupElementObserver() {
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Check if the added node or its children are GeoEngine elements
                    const geoElements = node.classList && 
                        node.classList.contains('geoengine-view') ? [node] :
                        node.querySelectorAll ? node.querySelectorAll(
                            '.geoengine-view, .geoengine-map-container, .geoengine-controls, .geoengine-layer-panel'
                        ) : [];
                    
                    if (geoElements.length > 0) {
                        Array.from(geoElements).forEach(element => {
                            element.classList.add('geoengine-themed');
                            
                            // Inherit theme from body/html
                            const bodyTheme = document.body.getAttribute('data-bs-theme') || 
                                             document.documentElement.getAttribute('data-bs-theme');
                            if (bodyTheme && !element.getAttribute('data-bs-theme')) {
                                element.setAttribute('data-bs-theme', bodyTheme);
                            }
                        });
                    }
                }
            });
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}

/**
 * Set up listener for theme changes
 */
function setupThemeChangeListener() {
    // Observer for data-bs-theme changes on body/html
    const themeObserver = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'attributes' && mutation.attributeName === 'data-bs-theme') {
                const newTheme = mutation.target.getAttribute('data-bs-theme');
                updateGeoEngineTheme(newTheme);
            }
        });
    });
    
    // Watch both body and html for theme changes
    themeObserver.observe(document.body, { 
        attributes: true, 
        attributeFilter: ['data-bs-theme'] 
    });
    
    themeObserver.observe(document.documentElement, { 
        attributes: true, 
        attributeFilter: ['data-bs-theme'] 
    });
    
    // Listen for custom Odoo theme events (if any)
    document.addEventListener('theme-changed', function(event) {
        updateGeoEngineTheme(event.detail.theme);
    });
}

/**
 * Update theme for all GeoEngine elements
 */
function updateGeoEngineTheme(theme) {
    const geoElements = document.querySelectorAll('.geoengine-themed');
    
    geoElements.forEach(element => {
        if (theme) {
            element.setAttribute('data-bs-theme', theme);
        } else {
            element.removeAttribute('data-bs-theme');
        }
    });
    
    // Dispatch event for any GeoEngine components that need to react to theme changes
    const event = new CustomEvent('geoengine-theme-updated', {
        detail: { theme: theme },
        bubbles: true
    });
    document.dispatchEvent(event);
}

// Export for potential external usage
window.GeoEngineTheme = {
    applyThemeClasses,
    updateGeoEngineTheme
};