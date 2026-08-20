#!/usr/bin/env bash
# Scales all ECS services to 0 to stop Fargate compute charges, without
# destroying anything — ALB, EFS (HF model cache), S3 bucket, and ECR images
# all persist. Cheaper and faster to reverse than teardown.sh/deploy.sh.
set -euo pipefail
cd "$(dirname "$0")"

CLUSTER=$(terraform output -raw ecs_cluster_name)
REGION=$(terraform output -raw aws_region)

for svc in frontend worker backend redis; do
  echo "==> Scaling $svc to 0"
  aws ecs update-service --cluster "$CLUSTER" --service "$svc" --desired-count 0 --region "$REGION" >/dev/null
done

echo "Done. Services are scaled to 0 — no more Fargate compute charges until you run resume.sh."
