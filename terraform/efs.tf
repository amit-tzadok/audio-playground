# Model weights (pyannote diarization ~1-2GB gated download, Demucs
# ~80MB, faster-whisper base ~150MB) persist here across task
# restarts/redeploys — without this, every spin-up-before-a-demo cycle
# would re-download all of them from scratch, adding minutes of startup
# time each time, which defeats the point of the tear-down/spin-up workflow.
resource "aws_efs_file_system" "hf_cache" {
  creation_token = "${var.project_name}-hf-cache"

  tags = { Name = "${var.project_name}-hf-cache" }
}

resource "aws_security_group" "efs" {
  name        = "${var.project_name}-efs"
  description = "Allows NFS from the app tasks to the HF model cache."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "NFS from app tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_efs_mount_target" "hf_cache" {
  for_each        = toset(data.aws_subnets.default.ids)
  file_system_id  = aws_efs_file_system.hf_cache.id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}
