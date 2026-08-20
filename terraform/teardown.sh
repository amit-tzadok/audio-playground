#!/usr/bin/env bash
# Tears everything down to $0 in AWS charges. The next deploy.sh will get a
# fresh S3 bucket name and ALB DNS name — nothing here is meant to persist
# across a teardown/redeploy cycle.
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" != "-y" ]; then
  read -r -p "This will destroy the entire AWS deployment (ECS, ALB, EFS, ECR images, S3 bucket contents). Continue? [y/N] " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
  fi
fi

terraform destroy -input=false -auto-approve
