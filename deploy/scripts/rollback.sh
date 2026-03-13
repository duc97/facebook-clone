#!/usr/bin/env bash
# Manual rollback — switch service back to previous slot
set -euo pipefail

NAMESPACE="${1:?namespace required}"
APP_NAME="${2:?app-name required}"

CURRENT_SLOT=$(kubectl get service "${APP_NAME}" \
  -n "${NAMESPACE}" \
  -o jsonpath='{.spec.selector.slot}')

if [[ "${CURRENT_SLOT}" == "blue" ]]; then
  ROLLBACK_SLOT="green"
else
  ROLLBACK_SLOT="blue"
fi

echo "Rolling back from ${CURRENT_SLOT} → ${ROLLBACK_SLOT}"
kubectl patch service "${APP_NAME}" \
  -n "${NAMESPACE}" \
  -p "{\"spec\":{\"selector\":{\"app\":\"${APP_NAME}\",\"slot\":\"${ROLLBACK_SLOT}\"}}}"

echo "Rollback complete. Traffic now on ${ROLLBACK_SLOT}."
