// Application Configuration
// Configure REACT_APP_API_URL to point to your Azure Functions backend

const config = {
    // Azure Functions API base URL
    // Replace this with your actual Azure Functions endpoint
    // Example: "https://your-function-app.azurewebsites.net/api"
    API_URL: window.REACT_APP_API_URL || "https://your-azure-function-app.azurewebsites.net/api",
    
    // API endpoints
    ENDPOINTS: {
        SEARCH: "/Search",
        CHAT: "/Chat"
    }
};

// Helper function to build API URLs
function getApiUrl(endpoint) {
    return `${config.API_URL}${endpoint}`;
}

// Export config for use in other scripts
window.AppConfig = config;
window.getApiUrl = getApiUrl;
