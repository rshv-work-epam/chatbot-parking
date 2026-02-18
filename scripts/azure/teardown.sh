#!/usr/bin/env bash
set -euo pipefail

RG="${AZURE_RESOURCE_GROUP:-rg-chatbot-parking-v2}"
SUB="${AZURE_SUBSCRIPTION_ID:-}"
DELETE_BUDGET="false"
BUDGET_NAME="${BUDGET_NAME:-chatbot-parking-10usd}"

usage() {
  cat <<EOF
Usage: $0 [--resource-group <name>] [--subscription <id>] [--delete-budget] [--budget-name <name>]

Deletes the Azure resource group for this chatbot demo. Optional: delete the subscription budget.

Examples:
  $0 --resource-group rg-chatbot-parking-v2
  $0 --delete-budget --budget-name chatbot-parking-10usd
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group)
      RG="$2"; shift 2;;
    --subscription)
      SUB="$2"; shift 2;;
    --delete-budget)
      DELETE_BUDGET="true"; shift;;
    --budget-name)
      BUDGET_NAME="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2;;
  esac
done

if [[ -n "$SUB" ]]; then
  az account set --subscription "$SUB" >/dev/null
fi

echo "Teardown"
echo "- Subscription: $(az account show --query id -o tsv)"
echo "- Resource group: $RG"

if [[ "$DELETE_BUDGET" == "true" ]]; then
  echo "Deleting budget (best-effort): $BUDGET_NAME"
  az consumption budget delete --budget-name "$BUDGET_NAME" --subscription "$(az account show --query id -o tsv)" >/dev/null 2>&1 || true
fi

echo "Deleting resource group (async)..."
az group delete --name "$RG" --yes --no-wait
echo "Requested deletion. Use: az group show -n \"$RG\" to check status."

