variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for naming every resource this config creates."
  type        = string
  default     = "audio-platform"
}

variable "hf_token" {
  description = "Hugging Face access token (needs access to pyannote/speaker-diarization-3.1)."
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key, used by the natural-language pace-adjustment feature."
  type        = string
  sensitive   = true
}

variable "basic_auth_htpasswd" {
  description = "Pre-generated htpasswd contents (e.g. from `htpasswd -nB user`) gating access to the frontend."
  type        = string
  sensitive   = true
}

variable "backend_image_tag" {
  description = "Image tag to deploy for the backend/worker image (same image, different container command)."
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Image tag to deploy for the frontend image."
  type        = string
  default     = "latest"
}

variable "worker_cpu" {
  description = "Fargate vCPU units for the worker task (1024 = 1 vCPU). Demucs + pyannote + faster-whisper models stay resident in memory once loaded, so this is the resource-heavy task."
  type        = number
  default     = 2048
}

variable "worker_memory" {
  description = "Fargate memory (MB) for the worker task."
  type        = number
  default     = 8192
}

variable "backend_cpu" {
  type    = number
  default = 512
}

variable "backend_memory" {
  type    = number
  default = 1024
}

variable "frontend_cpu" {
  type    = number
  default = 256
}

variable "frontend_memory" {
  type    = number
  default = 512
}
