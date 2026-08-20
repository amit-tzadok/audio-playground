#!/usr/bin/env bash
# Spins the whole stack up: creates ECR repos first (chicken-and-egg fix —
# the ECS services need images to exist before they'll start cleanly),
# builds + pushes images, then applies everything else.
set -euo pipefail
cd "$(dirname "$0")"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS CLI isn't configured (or credentials are invalid)." >&2
  echo "Run: aws configure" >&2
  exit 1
fi

if [ ! -f terraform.tfvars ]; then
  echo "terraform.tfvars not found — copy terraform.tfvars.example and fill in real values first." >&2
  exit 1
fi

terraform init -input=false

echo "==> Creating ECR repositories first (images need somewhere to land before the ECS services can start)"
terraform apply -input=false -auto-approve \
  -target=aws_ecr_repository.backend \
  -target=aws_ecr_repository.frontend

BACKEND_REPO=$(terraform output -raw ecr_backend_repo_url)
FRONTEND_REPO=$(terraform output -raw ecr_frontend_repo_url)
REGION=$(terraform output -raw aws_region)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "==> Logging in to ECR"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

echo "==> Building and pushing backend image (used by both the backend and worker services)"
docker build --platform linux/amd64 -t "$BACKEND_REPO:latest" ../backend
docker push "$BACKEND_REPO:latest"

echo "==> Building and pushing frontend image"
docker build --platform linux/amd64 -t "$FRONTEND_REPO:latest" ../frontend
docker push "$FRONTEND_REPO:latest"

echo "==> Applying the rest of the infrastructure"
terraform apply -input=false -auto-approve

echo ""
echo "==> Done. App URL:"
terraform output -raw app_url
echo ""
echo "(ECS services can take a minute or two to pass health checks after this — the URL may 502 briefly.)"
