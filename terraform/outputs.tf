output "app_url" {
  description = "Public URL for the app."
  value       = "http://${aws_lb.this.dns_name}"
}

output "ecr_backend_repo_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repo_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "s3_bucket_name" {
  value = aws_s3_bucket.audio.bucket
}

output "aws_region" {
  value = var.aws_region
}
