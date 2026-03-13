#!/usr/bin/env bash
# Blue/Green deployment for Kubernetes
# Usage: blue-green-deploy.sh <namespace> <image> <app-name>
set -euo pipefail

NAMESPACE="${1:?namespace required}"
IMAGE="${2:?image required}"
APP_NAME="${3:?app-name required}"

echo "=== Blue/Green Deploy ==="
echo "  Namespace : ${NAMESPACE}"
echo "  Image     : ${IMAGE}"
echo "  App       : ${APP_NAME}"

# Determine current active slot (blue or green)
CURRENT_SLOT=$(kubectl get service "${APP_NAME}" \
  -n "${NAMESPACE}" \
  -o jsonpath='{.spec.selector.slot}' 2>/dev/null || echo "blue")

if [[ "${CURRENT_SLOT}" == "blue" ]]; then
  NEW_SLOT="green"
else
  NEW_SLOT="blue"
fi

DEPLOY_NAME="${APP_NAME}-${NEW_SLOT}"

echo "  Current slot : ${CURRENT_SLOT}"
echo "  New slot     : ${NEW_SLOT}"

# Update the inactive deployment with new image
kubectl set image deployment/"${DEPLOY_NAME}" \
  app="${IMAGE}" \
  -n "${NAMESPACE}"

# Wait for rollout
echo "Waiting for ${DEPLOY_NAME} rollout..."
kubectl rollout status deployment/"${DEPLOY_NAME}" \
  -n "${NAMESPACE}" \
  --timeout=300s

# Run readiness check
echo "Verifying readiness..."
READY_PODS=$(kubectl get deployment "${DEPLOY_NAME}" \
  -n "${NAMESPACE}" \
  -o jsonpath='{.status.readyReplicas}')

if [[ "${READY_PODS}" -lt 1 ]]; then
  echo "ERROR: No ready pods in ${DEPLOY_NAME}"
  exit 1
fi

# Switch service traffic to new slot
echo "Switching traffic to ${NEW_SLOT}..."
kubectl patch service "${APP_NAME}" \
  -n "${NAMESPACE}" \
  -p "{\"spec\":{\"selector\":{\"app\":\"${APP_NAME}\",\"slot\":\"${NEW_SLOT}\"}}}"

echo "=== Deploy complete: traffic now on ${NEW_SLOT} ==="
echo "Previous slot (${CURRENT_SLOT}) kept for rollback."
echo "To rollback: kubectl patch service ${APP_NAME} -n ${NAMESPACE} -p '{\"spec\":{\"selector\":{\"app\":\"${APP_NAME}\",\"slot\":\"${CURRENT_SLOT}\"}}}'  "
