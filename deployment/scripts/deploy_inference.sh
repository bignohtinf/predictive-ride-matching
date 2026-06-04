#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:=ap-southeast-1}"
: "${PROJECT:=crp}"
: "${ENV:=dev}"
: "${NAMESPACE:=crp-inference}"
: "${RELEASE_NAME:=crp-inference}"
: "${CHART_PATH:=../../infrastructure/helm/crp-inference}"

: "${EKS_CLUSTER_NAME:?Missing EKS_CLUSTER_NAME}"
: "${INFERENCE_IMAGE_URI:?Missing INFERENCE_IMAGE_URI}"
: "${MODEL_S3_URI:?Missing MODEL_S3_URI}"
: "${REDIS_ENDPOINT:?Missing REDIS_ENDPOINT}"
: "${REDIS_AUTH_TOKEN:?Missing REDIS_AUTH_TOKEN}"

IMAGE_REPOSITORY="$(echo "${INFERENCE_IMAGE_URI}" | cut -d: -f1)"
IMAGE_TAG="$(echo "${INFERENCE_IMAGE_URI}" | cut -d: -f2-)"

echo "Updating kubeconfig for cluster: ${EKS_CLUSTER_NAME}"
aws eks update-kubeconfig \
  --region "${AWS_REGION}" \
  --name "${EKS_CLUSTER_NAME}"

echo "Creating namespace if missing: ${NAMESPACE}"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo "Deploying Helm release: ${RELEASE_NAME}"
helm upgrade --install "${RELEASE_NAME}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --set image.repository="${IMAGE_REPOSITORY}" \
  --set image.tag="${IMAGE_TAG}" \
  --set model.s3Uri="${MODEL_S3_URI}" \
  --set redis.endpoint="${REDIS_ENDPOINT}" \
  --set redis.authToken="${REDIS_AUTH_TOKEN}" \
  --wait \
  --timeout 10m

echo "Checking rollout status..."
kubectl rollout status deployment/"${RELEASE_NAME}" \
  --namespace "${NAMESPACE}" \
  --timeout=10m

echo "Deployment completed."
