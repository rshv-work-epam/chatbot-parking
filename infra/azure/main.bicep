@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Name of Azure Container Registry')
param acrName string

@description('Container Apps environment name')
param containerAppsEnvironmentName string = 'chatbot-parking-env'

@description('UI container app name')
param uiContainerAppName string = 'chatbot-parking-ui'

@description('Function app name')
param functionAppName string = 'chatbot-parking-func'

@description('Storage account for Function App (must be globally unique)')
param functionStorageAccountName string = 'chatbotparkst${uniqueString(resourceGroup().id)}'

@description('Container CPU cores')
param cpu string = '0.5'

@description('Container memory')
param memory string = '1.0Gi'

@description('Deploy Azure Cosmos DB SQL API for reservations and chat state')
param deployCosmosDb bool = true

@description('Cosmos DB account name (must be globally unique)')
param cosmosAccountName string = 'chatbotparking-cosmos-${uniqueString(resourceGroup().id)}'

@description('Cosmos DB SQL database name')
param cosmosDatabaseName string = 'chatbotParking'

@description('Cosmos DB SQL container for chat threads')
param cosmosThreadsContainerName string = 'threads'

@description('Cosmos DB SQL container for admin approvals')
param cosmosApprovalsContainerName string = 'approvals'

@description('Cosmos DB SQL container for reservation records')
param cosmosReservationsContainerName string = 'reservations'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = if (deployCosmosDb) {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource cosmosSqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = if (deployCosmosDb) {
  parent: cosmosAccount
  name: cosmosDatabaseName
  properties: {
    resource: {
      id: cosmosDatabaseName
    }
  }
}

resource cosmosThreadsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = if (deployCosmosDb) {
  parent: cosmosSqlDatabase
  name: cosmosThreadsContainerName
  properties: {
    resource: {
      id: cosmosThreadsContainerName
      partitionKey: {
        paths: [
          '/thread_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
    }
  }
}

resource cosmosApprovalsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = if (deployCosmosDb) {
  parent: cosmosSqlDatabase
  name: cosmosApprovalsContainerName
  properties: {
    resource: {
      id: cosmosApprovalsContainerName
      partitionKey: {
        paths: [
          '/request_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
    }
  }
}

resource cosmosReservationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = if (deployCosmosDb) {
  parent: cosmosSqlDatabase
  name: cosmosReservationsContainerName
  properties: {
    resource: {
      id: cosmosReservationsContainerName
      partitionKey: {
        paths: [
          '/partition_key'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
    }
  }
}

resource functionStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: functionStorageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource functionPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'asp-${functionAppName}'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${functionStorage.name};AccountKey=${functionStorage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'COSMOS_DB_ENDPOINT'
          value: deployCosmosDb ? cosmosAccount.properties.documentEndpoint : ''
        }
        {
          name: 'COSMOS_DB_KEY'
          value: deployCosmosDb ? cosmosAccount.listKeys().primaryMasterKey : ''
        }
        {
          name: 'COSMOS_DB_DATABASE'
          value: deployCosmosDb ? cosmosDatabaseName : ''
        }
        {
          name: 'COSMOS_DB_CONTAINER_THREADS'
          value: deployCosmosDb ? cosmosThreadsContainerName : ''
        }
        {
          name: 'COSMOS_DB_CONTAINER_APPROVALS'
          value: deployCosmosDb ? cosmosApprovalsContainerName : ''
        }
        {
          name: 'COSMOS_DB_CONTAINER_RESERVATIONS'
          value: deployCosmosDb ? cosmosReservationsContainerName : ''
        }
        {
          name: 'PERSISTENCE_BACKEND'
          value: deployCosmosDb ? 'cosmos' : 'memory'
        }
        // Budget auto-stop configuration. Used by infra/azure/durable_functions/function_app.py (route: /api/budget/stop).
        {
          name: 'AUTO_STOP_SUBSCRIPTION_ID'
          value: subscription().subscriptionId
        }
        {
          name: 'AUTO_STOP_RESOURCE_GROUP'
          value: resourceGroup().name
        }
        {
          name: 'AUTO_STOP_CONTAINER_APP_NAMES'
          value: uiContainerAppName
        }
        {
          name: 'AUTO_STOP_FUNCTION_APP_NAME'
          value: functionAppName
        }
        {
          name: 'AUTO_STOP_STOP_FUNCTION_APP'
          value: 'false'
        }
      ]
    }
  }
}

resource uiContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: uiContainerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: 'system'
        }
      ]
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: 'admin-ui-token'
          value: 'replace-at-deploy-time'
        }
        {
          name: 'durable-function-key'
          value: listkeys('${functionApp.id}/host/default', '2023-12-01').functionKeys.default
        }
        {
          name: 'cosmos-db-key'
          value: deployCosmosDb ? cosmosAccount.listKeys().primaryMasterKey : ''
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ui-api'
          image: '${acrName}.azurecr.io/chatbot-parking-ui:latest'
          command: [
            'bash'
          ]
          args: [
            '-lc'
            'uvicorn chatbot_parking.web_demo_server:app --host 0.0.0.0 --port 8000'
          ]
          env: [
            {
              name: 'DURABLE_BASE_URL'
              value: 'https://${functionApp.properties.defaultHostName}'
            }
            {
              name: 'DURABLE_FUNCTION_KEY'
              secretRef: 'durable-function-key'
            }
            {
              name: 'ADMIN_UI_TOKEN'
              secretRef: 'admin-ui-token'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
              value: deployCosmosDb ? cosmosAccount.properties.documentEndpoint : ''
            }
            {
              name: 'COSMOS_DB_KEY'
              secretRef: 'cosmos-db-key'
            }
            {
              name: 'COSMOS_DB_DATABASE'
              value: deployCosmosDb ? cosmosDatabaseName : ''
            }
            {
              name: 'COSMOS_DB_CONTAINER_THREADS'
              value: deployCosmosDb ? cosmosThreadsContainerName : ''
            }
            {
              name: 'COSMOS_DB_CONTAINER_APPROVALS'
              value: deployCosmosDb ? cosmosApprovalsContainerName : ''
            }
            {
              name: 'COSMOS_DB_CONTAINER_RESERVATIONS'
              value: deployCosmosDb ? cosmosReservationsContainerName : ''
            }
            {
              name: 'PERSISTENCE_BACKEND'
              value: deployCosmosDb ? 'cosmos' : 'memory'
            }
            {
              name: 'MCP_SERVER_COMMAND'
              value: 'python'
            }
            {
              name: 'MCP_SERVER_ARGS'
              value: '-m chatbot_parking.mcp_servers.reservations_stdio_server'
            }
          ]
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/admin/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

resource acrPullForUi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(uiContainerApp.id, acr.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: uiContainerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}

// Grant the Function App managed identity permission to stop the UI Container App (and optionally itself) when a cost budget triggers.
var contributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')

resource contributorForStopOnUi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(uiContainerApp.id, functionApp.identity.principalId, 'Contributor')
  scope: uiContainerApp
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: contributorRoleDefinitionId
    principalType: 'ServicePrincipal'
  }
}

resource contributorForStopOnFunction 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionApp.id, functionApp.identity.principalId, 'Contributor')
  scope: functionApp
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: contributorRoleDefinitionId
    principalType: 'ServicePrincipal'
  }
}

output uiApiUrl string = 'https://${uiContainerApp.properties.configuration.ingress.fqdn}'
output durableBaseUrl string = 'https://${functionApp.properties.defaultHostName}'
output acrLoginServer string = acr.properties.loginServer
output cosmosDbEndpoint string = deployCosmosDb ? cosmosAccount.properties.documentEndpoint : ''
output cosmosDbDatabase string = deployCosmosDb ? cosmosDatabaseName : ''
output cosmosDbThreadsContainer string = deployCosmosDb ? cosmosThreadsContainerName : ''
output cosmosDbApprovalsContainer string = deployCosmosDb ? cosmosApprovalsContainerName : ''
output cosmosDbReservationsContainer string = deployCosmosDb ? cosmosReservationsContainerName : ''
