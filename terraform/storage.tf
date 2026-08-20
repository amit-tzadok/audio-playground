# Random suffix so the bucket name doesn't collide with anyone else's
# (S3 bucket names are globally unique across all of AWS).
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "audio" {
  bucket = "${var.project_name}-audio-${random_id.bucket_suffix.hex}"
  # Scratch data for a demo app meant to be torn down repeatedly — let
  # `terraform destroy` delete the bucket even if it still has objects in
  # it, rather than failing and requiring a manual empty first.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "audio" {
  bucket                  = aws_s3_bucket.audio.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Uploaded/processed audio is scratch data for this demo app, not something
# worth keeping forever — auto-expire so storage cost can't creep up between
# teardown/spin-up cycles.
resource "aws_s3_bucket_lifecycle_configuration" "audio" {
  bucket = aws_s3_bucket.audio.id

  rule {
    id     = "expire-after-7-days"
    status = "Enabled"
    filter {}

    expiration {
      days = 7
    }
  }
}

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # let `terraform destroy` remove it even with images still in it

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}-frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the most recent few images per repo so ECR storage cost doesn't
# grow unbounded across repeated deploys.
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}
