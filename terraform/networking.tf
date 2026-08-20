# Uses the account's default VPC/subnets rather than provisioning a new one
# — reasonable scope for a demo/portfolio deployment; a production build
# would want its own VPC with private subnets for the tasks and a NAT
# gateway, at extra cost.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb"
  description = "Allows inbound HTTP from the internet to the ALB."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-alb" }
}

# One shared security group for all app tasks (backend, worker, frontend,
# redis): self-referencing ingress lets them all reach each other over
# Cloud Map service discovery, plus the ALB can reach the frontend task.
resource "aws_security_group" "app" {
  name        = "${var.project_name}-app"
  description = "ECS tasks — internal service-to-service traffic plus ALB to frontend."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "From the ALB (frontend task, port 80)"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Between app tasks (Cloud Map service discovery)"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "Outbound to pull images and reach HF Hub / Anthropic / YouTube"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-app" }
}
