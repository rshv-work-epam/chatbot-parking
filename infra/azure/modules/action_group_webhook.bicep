targetScope = 'resourceGroup'

@description('Action Group name (resource group scoped).')
param actionGroupName string

@description('Action Group short name (12 chars max).')
param actionGroupShortName string

@description('Webhook receiver URL for the action group.')
param webhookUrl string

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: actionGroupName
  location: 'global'
  properties: {
    enabled: true
    groupShortName: actionGroupShortName
    webhookReceivers: [
      {
        name: 'budgetStopWebhook'
        serviceUri: webhookUrl
        useCommonAlertSchema: true
      }
    ]
  }
}

output actionGroupResourceId string = actionGroup.id

