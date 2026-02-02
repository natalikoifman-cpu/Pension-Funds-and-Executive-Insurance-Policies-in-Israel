# Setup Guide

## Prerequisites

- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- [Azure Functions Core Tools v4](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- [Node.js 20+](https://nodejs.org/)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (for deployment)

## Local Development

### 1. Start the Backend (Azure Functions)

```bash
cd FunctionApp
dotnet restore
func start
```

The API will be available at `http://localhost:7071`

**Endpoints:**
- GET `http://localhost:7071/api/Search?query=מיטב`
- POST `http://localhost:7071/api/Chat`

### 2. Start the Frontend (React)

```bash
cd frontend
cp .env.example .env
npm install
npm start
```

The app will open at `http://localhost:3000`

---

## Deploy to Azure

### Step 1: Create Azure Resources

```bash
# Login to Azure
az login

# Create resource group
az group create --name pension-funds-rg --location westeurope

# Create storage account (required for Functions)
az storage account create \
  --name pensionfundsstorage \
  --resource-group pension-funds-rg \
  --location westeurope \
  --sku Standard_LRS

# Create Function App
az functionapp create \
  --name pension-funds-api \
  --resource-group pension-funds-rg \
  --consumption-plan-location westeurope \
  --runtime dotnet-isolated \
  --functions-version 4 \
  --storage-account pensionfundsstorage

# Create Static Web App
az staticwebapp create \
  --name pension-funds-web \
  --resource-group pension-funds-rg \
  --location westeurope
```

### Step 2: Configure GitHub Secrets

1. Go to your GitHub repository → Settings → Secrets and variables → Actions

2. Add these secrets:

   **For Backend (Function App):**
   - `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`: Download from Azure Portal → Function App → Get publish profile

   **For Frontend (Static Web App):**
   - `AZURE_STATIC_WEB_APPS_API_TOKEN`: Get from Azure Portal → Static Web App → Manage deployment token

3. Add repository variable:
   - Go to Settings → Secrets and variables → Actions → Variables
   - Add `API_URL`: `https://pension-funds-api.azurewebsites.net/api`

### Step 3: Deploy

Push to `main` branch - GitHub Actions will automatically deploy:
- Backend changes → Azure Functions
- Frontend changes → Azure Static Web Apps

---

## Manual Deployment

### Deploy Backend

```bash
cd FunctionApp
func azure functionapp publish pension-funds-api
```

### Deploy Frontend

```bash
cd frontend
npm run build
az staticwebapp upload --app-name pension-funds-web --app-location build
```

---

## URLs After Deployment

| Component | URL |
|-----------|-----|
| Frontend | `https://<static-web-app-name>.azurestaticapps.net` |
| Backend | `https://<function-app-name>.azurewebsites.net/api` |
