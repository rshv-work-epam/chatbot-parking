@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Name of Azure Container Registry')
param acrName string

@description('Container Apps environment name')
param containerAppsEnvironmentName string = 'chatbot-parking-env'

@description('Admin API container app name')
param adminContainerAppName string = 'chatbot-parking-admin'

@description('MCP server container app name')
param mcpContainerAppName string = 'chatbot-parking-mcp'

@description('Container CPU cores')
param cpu string = '0.5'

@description('Container memory')
param memory string = '1.0Gi'

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

resource adminContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: adminContainerAppName
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
          name: 'admin-api-token'
          value: 'replace-at-deploy-time'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'admin-api'
          image: '${acrName}.azurecr.io/chatbot-parking-admin:latest'
          command: [
            'bash'
          ]
          args: [
            '-lc'
            'uvicorn chatbot_parking.admin_api:app --host 0.0.0.0 --port 8000'
          ]
          env: [
            {
              name: 'ADMIN_API_TOKEN'
              secretRef: 'admin-api-token'
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

resource mcpContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: mcpContainerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8001
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
          name: 'mcp-api-token'
          value: 'replace-at-deploy-time'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp-server'
          image: '${acrName}.azurecr.io/chatbot-parking-mcp:latest'
          command: [
            'bash'
          ]
          args: [
            '-lc'
            'uvicorn chatbot_parking.mcp_server:app --host 0.0.0.0 --port 8001'
          ]
          env: [
            {
              name: 'MCP_API_TOKEN'
              secretRef: 'mcp-api-token'
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
                path: '/health'
                port: 8001
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

resource acrPullForAdmin 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(adminContainerApp.id, acr.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: adminContainerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}

resource acrPullForMcp 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(mcpContainerApp.id, acr.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: mcpContainerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalType: 'ServicePrincipal'
  }
}

output adminApiUrl string = 'https://${adminContainerApp.properties.configuration.ingress.fqdn}'
output mcpServerUrl string = 'https://${mcpContainerApp.properties.configuration.ingress.fqdn}'
output acrLoginServer string = acr.properties.loginServer
