#!/usr/bin/env bash
set -euo pipefail

RG="${1:-${AZURE_RESOURCE_GROUP:-rg-chatbot-parking-v2}}"
SUB="${AZURE_SUBSCRIPTION_ID:-}"

if [[ -n "$SUB" ]]; then
  az account set --subscription "$SUB" >/dev/null
fi

echo "Azure inventory"
echo "- Subscription: $(az account show --query id -o tsv)"
echo "- Tenant: $(az account show --query tenantId -o tsv)"
echo "- Resource group: $RG"
echo

if ! az group show --name "$RG" >/dev/null 2>&1; then
  echo "Resource group not found: $RG" >&2
  exit 2
fi

echo "Resources"
az resource list -g "$RG" --query "[].{name:name,type:type,location:location}" -o table
echo

UI_NAME="${UI_CONTAINER_APP_NAME:-chatbot-parking-ui}"
FUNC_NAME="${AZURE_FUNCTIONAPP_NAME:-chatbot-parking-func}"

FQDN="$(az containerapp show -g "$RG" -n "$UI_NAME" --query 'properties.configuration.ingress.fqdn' -o tsv 2>/dev/null || true)"
if [[ -n "${FQDN:-}" ]]; then
  echo "Endpoints"
  echo "- Chat UI:  https://${FQDN}/chat/ui"
  echo "- Admin UI: https://${FQDN}/admin/ui"
  echo "- Version:  https://${FQDN}/version"
  echo
fi

echo "Container App scale"
az containerapp show -g "$RG" -n "$UI_NAME" --query "{min:properties.template.scale.minReplicas,max:properties.template.scale.maxReplicas}" -o table 2>/dev/null || true
echo

echo "Budgets (subscription scope)"
az consumption budget list --subscription "$(az account show --query id -o tsv)" -o table 2>/dev/null || true
echo

echo "Action groups (subscription)"
az monitor action-group list --subscription "$(az account show --query id -o tsv)" -o table 2>/dev/null || true
echo

echo "Function App (exists?)"
az functionapp show -g "$RG" -n "$FUNC_NAME" --query "{name:name,host:defaultHostName,state:state}" -o table 2>/dev/null || true

