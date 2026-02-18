targetScope = 'subscription'

@description('Name of the existing resource group that contains the Durable Function App.')
param resourceGroupName string

@description('Name of the existing Function App that exposes /api/budget/stop (see infra/azure/durable_functions/function_app.py).')
param functionAppName string

@description('Budget name (unique per scope).')
param budgetName string = 'chatbot-parking-10usd'

@description('Budget amount in the subscription billing currency (USD for most US accounts).')
param budgetAmount int = 10

@description('Budget start date in ISO-8601 format, e.g. 2026-02-01T00:00:00Z.')
param budgetStartDate string

@description('Budget end date in ISO-8601 format.')
param budgetEndDate string = '9999-12-31T00:00:00Z'

@description('Action Group name (resource group-scoped).')
param actionGroupName string = 'ag-chatbot-parking-budget-autostop'

@description('Action Group short name (12 chars max).')
param actionGroupShortName string = 'budgstop'

@description('Emails to notify when thresholds are reached.')
param contactEmails array = []

@description('Percent threshold (Actual) to trigger the auto-stop action. Use <100 to compensate for cost-data lag.')
@minValue(1)
@maxValue(100)
param stopThresholdPercent int = 90

@description('Also trigger at this percent threshold (Actual). Typically 100.')
@minValue(1)
@maxValue(100)
param hardThresholdPercent int = 100

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' existing = {
  name: resourceGroupName
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' existing = {
  name: functionAppName
  scope: rg
}

// Host key is used because it can authenticate multiple routes/functions in the app.
var functionHostKey = listKeys('${functionApp.id}/host/default', '2023-12-01').functionKeys.default
var stopFunctionUrl = 'https://${functionApp.properties.defaultHostName}/api/budget/stop?code=${functionHostKey}'

module actionGroup 'modules/action_group_webhook.bicep' = {
  name: 'budgetActionGroup'
  scope: rg
  params: {
    actionGroupName: actionGroupName
    actionGroupShortName: actionGroupShortName
    webhookUrl: stopFunctionUrl
  }
}

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: budgetName
  properties: {
    amount: budgetAmount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
      endDate: budgetEndDate
    }
    notifications: {
      'StopAt${stopThresholdPercent}Percent': {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: stopThresholdPercent
        thresholdType: 'Actual'
        contactEmails: contactEmails
        contactGroups: [
          actionGroup.outputs.actionGroupResourceId
        ]
      }
      'StopAt${hardThresholdPercent}Percent': {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: hardThresholdPercent
        thresholdType: 'Actual'
        contactEmails: contactEmails
        contactGroups: [
          actionGroup.outputs.actionGroupResourceId
        ]
      }
    }
  }
}

output budgetResourceId string = budget.id
output actionGroupResourceId string = actionGroup.outputs.actionGroupResourceId
