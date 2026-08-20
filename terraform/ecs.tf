locals {
  namespace_name     = "${var.project_name}.local"
  redis_dns          = "redis.${local.namespace_name}"
  backend_svc_dns    = "backend-svc.${local.namespace_name}"
  backend_image_url  = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
  frontend_image_url = "${aws_ecr_repository.frontend.repository_url}:${var.frontend_image_tag}"
}

resource "aws_ecs_cluster" "this" {
  name = var.project_name

  setting {
    name  = "containerInsights"
    value = "disabled" # extra CloudWatch cost not worth it for a demo cluster
  }
}

resource "aws_service_discovery_private_dns_namespace" "this" {
  name = local.namespace_name
  vpc  = data.aws_vpc.default.id
}

resource "aws_service_discovery_service" "redis" {
  name = "redis"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.this.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
}

resource "aws_service_discovery_service" "backend" {
  name = "backend-svc"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.this.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
}

# ---------------------------------------------------------------- redis ---
resource "aws_ecs_task_definition" "redis" {
  family                   = "${var.project_name}-redis"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([
    {
      name         = "redis"
      image        = "redis:7"
      essential    = true
      portMappings = [{ containerPort = 6379, protocol = "tcp" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}/redis"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "redis"
          "awslogs-create-group"  = "true"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "redis" {
  name            = "redis"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.redis.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.redis.arn
  }
}

# -------------------------------------------------------------- backend ---
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name         = "backend"
      image        = local.backend_image_url
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "CELERY_BROKER_URL", value = "redis://${local.redis_dns}:6379/0" },
        { name = "CELERY_RESULT_BACKEND", value = "redis://${local.redis_dns}:6379/0" },
        { name = "S3_BUCKET", value = aws_s3_bucket.audio.bucket },
      ]
      secrets = [
        { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic_api_key.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}/backend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
          "awslogs-create-group"  = "true"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "backend" {
  name            = "backend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.backend.arn
  }

  depends_on = [aws_ecs_service.redis]
}

# --------------------------------------------------------------- worker ---
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  volume {
    name = "hf-cache"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.hf_cache.id
      root_directory = "/"
    }
  }

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = local.backend_image_url
      essential = true
      command   = ["celery", "-A", "app.main.celery", "worker", "--loglevel=info"]
      environment = [
        { name = "CELERY_BROKER_URL", value = "redis://${local.redis_dns}:6379/0" },
        { name = "CELERY_RESULT_BACKEND", value = "redis://${local.redis_dns}:6379/0" },
        { name = "S3_BUCKET", value = aws_s3_bucket.audio.bucket },
      ]
      secrets = [
        { name = "HF_TOKEN", valueFrom = aws_secretsmanager_secret.hf_token.arn },
      ]
      mountPoints = [
        { sourceVolume = "hf-cache", containerPath = "/root/.cache/huggingface", readOnly = false },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}/worker"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
          "awslogs-create-group"  = "true"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name            = "worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  depends_on = [aws_ecs_service.redis, aws_efs_mount_target.hf_cache]
}

# ------------------------------------------------------------- frontend ---
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = aws_iam_role.execution.arn

  container_definitions = jsonencode([
    {
      name         = "frontend"
      image        = local.frontend_image_url
      essential    = true
      portMappings = [{ containerPort = 80, protocol = "tcp" }]
      environment = [
        { name = "BACKEND_HOST", value = local.backend_svc_dns },
        { name = "NGINX_ENVSUBST_FILTER", value = "^BACKEND_HOST$" },
      ]
      secrets = [
        { name = "BASIC_AUTH_HTPASSWD", valueFrom = aws_secretsmanager_secret.basic_auth_htpasswd.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}/frontend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "frontend"
          "awslogs-create-group"  = "true"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "frontend" {
  name            = "frontend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 80
  }

  depends_on = [aws_lb_listener.http, aws_ecs_service.backend]
}
