@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Deployment environment name used for naming and tags (e.g. dev, prod)')
@allowed([
  'dev'
  'prod'
])
param environment string

@description('Name of Azure Container Registry')
param acrName string

@description('Container Apps environment name')
param containerAppsEnvironmentName string = 'chatbot-parking-${environment}-env'

@description('Admin API container app name')
param adminContainerAppName string = 'chatbot-parking-${environment}-admin'

@description('MCP server container app name')
param mcpContainerAppName string = 'chatbot-parking-${environment}-mcp'

@description('CPU cores per container app replica')
param cpu string = '0.5'

@description('Memory per container app replica')
param memory string = '1.0Gi'

@description('Static admin API token stored as a Key Vault secret value at deploy time')
@secure()
param adminApiToken string

@description('Static MCP API token stored as a Key Vault secret value at deploy time')
@secure()
param mcpApiToken string

@description('Name of existing virtual network used by Application Gateway')
param vnetName string = 'chatbot-parking-${environment}-vnet'

@description('Address space for the virtual network')
param vnetAddressPrefix string = '10.20.0.0/16'

@description('Address prefix for the Application Gateway subnet')
param appGatewaySubnetPrefix string = '10.20.1.0/24'

var nameSuffix = '${environment}-${uniqueString(resourceGroup().id)}'
var appGatewayName = 'agw-chatbot-${environment}'
var wafPolicyName = 'waf-chatbot-${environment}'
var keyVaultName = take('kvchatbot${replace(environment, '-', '')}${uniqueString(resourceGroup().id)}', 24)
var logAnalyticsName = 'law-${nameSuffix}'
var appInsightsName = 'appi-chatbot-${environment}'
var publicIpName = 'pip-chatbot-${environment}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
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
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    softDeleteRetentionInDays: 90
  }
}

resource adminApiTokenSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVault.name}/admin-api-token'
  properties: {
    value: adminApiToken
  }
}

resource mcpApiTokenSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVault.name}/mcp-api-token'
  properties: {
    value: mcpApiToken
  }
}

resource adminContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: adminContainerAppName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
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
          keyVaultUrl: adminApiTokenSecret.properties.secretUriWithVersion
          identity: 'system'
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
              name: 'APP_ENV'
              value: environment
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
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
        minReplicas: environment == 'prod' ? 2 : 1
        maxReplicas: environment == 'prod' ? 6 : 3
      }
    }
  }
}

resource mcpContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: mcpContainerAppName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
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
          keyVaultUrl: mcpApiTokenSecret.properties.secretUriWithVersion
          identity: 'system'
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
              name: 'APP_ENV'
              value: environment
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
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
        minReplicas: environment == 'prod' ? 2 : 1
        maxReplicas: environment == 'prod' ? 6 : 3
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

resource keyVaultSecretsUserForAdmin 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(adminContainerApp.id, keyVault.id, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    principalId: adminContainerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalType: 'ServicePrincipal'
  }
}

resource keyVaultSecretsUserForMcp 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(mcpContainerApp.id, keyVault.id, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    principalId: mcpContainerApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalType: 'ServicePrincipal'
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'appgw-subnet'
        properties: {
          addressPrefix: appGatewaySubnetPrefix
        }
      }
    ]
  }
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2023-09-01' = {
  name: publicIpName
  location: location
  sku: {
    name: 'Standard'
  }
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource wafPolicy 'Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies@2023-09-01' = {
  name: wafPolicyName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    policySettings: {
      state: 'Enabled'
      mode: environment == 'prod' ? 'Prevention' : 'Detection'
      requestBodyCheck: true
      fileUploadLimitInMb: 100
      maxRequestBodySizeInKb: 128
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'OWASP'
          ruleSetVersion: '3.2'
        }
      ]
    }
  }
}

resource appGateway 'Microsoft.Network/applicationGateways@2023-09-01' = {
  name: appGatewayName
  location: location
  tags: {
    environment: environment
    workload: 'chatbot-parking'
  }
  properties: {
    sku: {
      name: 'WAF_v2'
      tier: 'WAF_v2'
      capacity: environment == 'prod' ? 2 : 1
    }
    gatewayIPConfigurations: [
      {
        name: 'appGwIpConfig'
        properties: {
          subnet: {
            id: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'appgw-subnet')
          }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'appGwFrontendIp'
        properties: {
          PublicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
    frontendPorts: [
      {
        name: 'httpPort'
        properties: {
          port: 80
        }
      }
    ]
    backendAddressPools: [
      {
        name: 'adminBackendPool'
        properties: {
          backendAddresses: [
            {
              fqdn: adminContainerApp.properties.configuration.ingress.fqdn
            }
          ]
        }
      }
      {
        name: 'mcpBackendPool'
        properties: {
          backendAddresses: [
            {
              fqdn: mcpContainerApp.properties.configuration.ingress.fqdn
            }
          ]
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'httpsSettings8000'
        properties: {
          port: 443
          protocol: 'Https'
          requestTimeout: 30
          pickHostNameFromBackendAddress: true
          probe: {
            id: resourceId('Microsoft.Network/applicationGateways/probes', appGateway.name, 'adminProbe')
          }
        }
      }
      {
        name: 'httpsSettings8001'
        properties: {
          port: 443
          protocol: 'Https'
          requestTimeout: 30
          pickHostNameFromBackendAddress: true
          probe: {
            id: resourceId('Microsoft.Network/applicationGateways/probes', appGateway.name, 'mcpProbe')
          }
        }
      }
    ]
    probes: [
      {
        name: 'adminProbe'
        properties: {
          protocol: 'Https'
          path: '/admin/health'
          interval: 30
          timeout: 30
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
          match: {
            statusCodes: [
              '200-399'
            ]
          }
        }
      }
      {
        name: 'mcpProbe'
        properties: {
          protocol: 'Https'
          path: '/health'
          interval: 30
          timeout: 30
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
          match: {
            statusCodes: [
              '200-399'
            ]
          }
        }
      }
    ]
    httpListeners: [
      {
        name: 'httpListener'
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appGateway.name, 'appGwFrontendIp')
          }
          frontendPort: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGateway.name, 'httpPort')
          }
          protocol: 'Http'
        }
      }
    ]
    urlPathMaps: [
      {
        name: 'chatbotPathMap'
        properties: {
          defaultBackendAddressPool: {
            id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGateway.name, 'adminBackendPool')
          }
          defaultBackendHttpSettings: {
            id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGateway.name, 'httpsSettings8000')
          }
          pathRules: [
            {
              name: 'adminRule'
              properties: {
                paths: [
                  '/admin/*'
                ]
                backendAddressPool: {
                  id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGateway.name, 'adminBackendPool')
                }
                backendHttpSettings: {
                  id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGateway.name, 'httpsSettings8000')
                }
              }
            }
            {
              name: 'mcpRule'
              properties: {
                paths: [
                  '/mcp/*'
                  '/health'
                ]
                backendAddressPool: {
                  id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGateway.name, 'mcpBackendPool')
                }
                backendHttpSettings: {
                  id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGateway.name, 'httpsSettings8001')
                }
              }
            }
          ]
        }
      }
    ]
    requestRoutingRules: [
      {
        name: 'pathRule'
        properties: {
          priority: 100
          ruleType: 'PathBasedRouting'
          httpListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appGateway.name, 'httpListener')
          }
          urlPathMap: {
            id: resourceId('Microsoft.Network/applicationGateways/urlPathMaps', appGateway.name, 'chatbotPathMap')
          }
        }
      }
    ]
    webApplicationFirewallConfiguration: {
      enabled: true
      firewallMode: environment == 'prod' ? 'Prevention' : 'Detection'
      ruleSetType: 'OWASP'
      ruleSetVersion: '3.2'
    }
    firewallPolicy: {
      id: wafPolicy.id
    }
  }
}

resource containerEnvDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${containerAppsEnvironment.name}'
  scope: containerAppsEnvironment
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource appGatewayDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${appGateway.name}'
  scope: appGateway
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      {
        category: 'ApplicationGatewayAccessLog'
        enabled: true
      }
      {
        category: 'ApplicationGatewayPerformanceLog'
        enabled: true
      }
      {
        category: 'ApplicationGatewayFirewallLog'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output adminApiUrl string = 'https://${adminContainerApp.properties.configuration.ingress.fqdn}'
output mcpServerUrl string = 'https://${mcpContainerApp.properties.configuration.ingress.fqdn}'
output wafPublicIp string = publicIp.properties.ipAddress
output keyVaultName string = keyVault.name
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString
output acrLoginServer string = acr.properties.loginServer
