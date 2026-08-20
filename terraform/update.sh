#!/usr/bin/env bash
# For pushing a code change to an already-running deployment — rebuilds
# and pushes both images, then forces ECS to redeploy with the new image
# (same tag, so a plain `docker push` wouldn't otherwise be noticed).
set -euo pipefail
cd "$(dirname "$0")"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS CLI isn't configured (or credentials are invalid)." >&2
  exit 1
fi

BACKEND_REPO=$(terraform output -raw ecr_backend_repo_url)
FRONTEND_REPO=$(terraform output -raw ecr_frontend_repo_url)
REGION=$(terraform output -raw aws_region)
CLUSTER=$(terraform output -raw ecs_cluster_name)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

echo "==> Building and pushing backend image"
docker build --platform linux/amd64 -t "$BACKEND_REPO:latest" ../backend
docker push "$BACKEND_REPO:latest"

echo "==> Building and pushing frontend image"
docker build --platform linux/amd64 -t "$FRONTEND_REPO:latest" ../frontend
docker push "$FRONTEND_REPO:latest"

echo "==> Forcing new deployments (backend, worker, frontend)"
for svc in backend worker frontend; do
  aws ecs update-service --cluster "$CLUSTER" --service "$svc" --force-new-deployment --region "$REGION" >/dev/null
done

echo "Done — ECS is rolling out the new images now (takes a minute or two)."
