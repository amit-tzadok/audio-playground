resource "aws_secretsmanager_secret" "hf_token" {
  name                    = "${var.project_name}/hf-token"
  recovery_window_in_days = 0 # demo project — allow immediate delete on teardown, not a 7/30-day hold
}

resource "aws_secretsmanager_secret_version" "hf_token" {
  secret_id     = aws_secretsmanager_secret.hf_token.id
  secret_string = var.hf_token
}

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name                    = "${var.project_name}/anthropic-api-key"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "anthropic_api_key" {
  secret_id     = aws_secretsmanager_secret.anthropic_api_key.id
  secret_string = var.anthropic_api_key
}

resource "aws_secretsmanager_secret" "basic_auth_htpasswd" {
  name                    = "${var.project_name}/basic-auth-htpasswd"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "basic_auth_htpasswd" {
  secret_id     = aws_secretsmanager_secret.basic_auth_htpasswd.id
  secret_string = var.basic_auth_htpasswd
}
