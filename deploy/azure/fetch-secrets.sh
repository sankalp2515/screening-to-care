#!/usr/bin/env bash
# Runs on the server. Reads secrets from Azure Key Vault with the server's managed identity (no stored
# credential) and writes /opt/tasleem/secrets.env, readable by root only. Prints no secret.
set -euo pipefail
VAULT="${KEY_VAULT:?set KEY_VAULT}"
OUT=/opt/tasleem/secrets.env
TOKEN=$(curl -sf -H Metadata:true \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fvault.azure.net" \
  | jq -r .access_token)
get() { curl -sf -H "Authorization: Bearer $TOKEN" "https://$VAULT.vault.azure.net/secrets/$1?api-version=7.4" | jq -r .value; }
umask 077
tmp=$(mktemp)
{
  echo "CORE_DB_URL=$(get core-db-url)"
  echo "NOTIFIER_DB_URL=$(get notifier-db-url)"
  echo "AGENT_DB_URL=$(get agent-db-url)"
  echo "CORE_INTEGRATION_KEYS=$(get core-integration-keys)"
  echo "NOTIFIER_KEY=$(get notifier-key)"
  echo "CONNECTOR_KEY=$(get connector-key)"
  echo "AZURE_OPENAI_API_KEY=$(get azure-openai-key)"
  echo "AZURE_OPENAI_BASE_URL=$(get azure-openai-base-url)"
  echo "SITE_HOST=$(get site-host)"
} > "$tmp"
grep -q '=null$\|=$' "$tmp" && { echo "a Key Vault secret is missing" >&2; rm -f "$tmp"; exit 1; }
mv "$tmp" "$OUT"
echo "secrets written to $OUT"
