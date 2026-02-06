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

# Copy the example settings file and configure your Azure OpenAI credentials
cp local.settings.json.example local.settings.json
# Edit local.settings.json and set your AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY

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

### Step 1: Create Azure Function App

```bash
# Login to Azure
az login

# Create Function App (using existing resource group and storage)
az functionapp create \
  --name pension-funds-api \
  --resource-group rg-natali.koifman-9117 \
  --consumption-plan-location eastus2 \
  --runtime dotnet-isolated \
  --functions-version 4 \
  --storage-account 1qsc2efb

# Create Static Web App for frontend
az staticwebapp create \
  --name pension-funds-web \
  --resource-group rg-natali.koifman-9117 \
  --location eastus2
```

### Step 2: Configure Azure OpenAI Settings

```bash
# Set Azure AI Foundry configuration in Function App
az functionapp config appsettings set \
  --name pension-funds-api \
  --resource-group rg-natali.koifman-9117 \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://chain123456-resource.services.ai.azure.com/api/projects/chain123456" \
    AZURE_OPENAI_API_KEY="your-api-key" \
    AZURE_OPENAI_DEPLOYMENT="gpt-4o"
```

### Step 3: Configure GitHub Secrets

1. Go to your GitHub repository → Settings → Secrets and variables → Actions

2. Add these secrets:

   **For Backend (Function App):**
   - `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`: Download from Azure Portal → Function App → Get publish profile

   **For Frontend (Static Web App):**
   - `AZURE_STATIC_WEB_APPS_API_TOKEN`: Get from Azure Portal → Static Web App → Manage deployment token

3. Add repository variable:
   - Go to Settings → Secrets and variables → Actions → Variables
   - Add `API_URL`: `https://pension-funds-api.azurewebsites.net/api`

### Step 4: Deploy

Push to `main` branch - GitHub Actions will automatically deploy:
- Backend changes → Azure Functions
- Frontend changes → Azure Static Web Apps

---

## Manual Deployment

### Deploy Backend

```bash
cd FunctionApp
func azure functionapp publish pension-funds-api --resource-group rg-natali.koifman-9117
```

### Deploy Frontend

```bash
cd frontend
npm run build
az staticwebapp upload --app-name pension-funds-web --resource-group rg-natali.koifman-9117 --app-location dist
```

---

## URLs After Deployment

| Component | URL |
|-----------|-----|
| Frontend | `https://<static-web-app-name>.azurestaticapps.net` |
| Backend | `https://<function-app-name>.azurewebsites.net/api` |
