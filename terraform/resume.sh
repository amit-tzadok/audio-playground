#!/usr/bin/env bash
# Scales all ECS services back to 1, in dependency order (redis, then
# backend/worker, then frontend) to match the depends_on chain in ecs.tf.
set -euo pipefail
cd "$(dirname "$0")"

CLUSTER=$(terraform output -raw ecs_cluster_name)
REGION=$(terraform output -raw aws_region)

for svc in redis backend worker frontend; do
  echo "==> Scaling $svc to 1"
  aws ecs update-service --cluster "$CLUSTER" --service "$svc" --desired-count 1 --region "$REGION" >/dev/null
done

echo ""
echo "Done. Allow a minute or two for health checks to pass (worker also needs to reload ML models into memory)."
echo "App URL:"
terraform output -raw app_url
