#!/bin/sh
# Basic-auth is opt-in: only enabled when BASIC_AUTH_HTPASSWD is injected
# (ECS, from Secrets Manager). Local docker-compose leaves it unset, so
# this writes an empty/no-op auth.conf and nginx behaves exactly as before.
set -e

AUTH_CONF=/etc/nginx/auth.conf

if [ -n "$BASIC_AUTH_HTPASSWD" ]; then
  printf '%s\n' "$BASIC_AUTH_HTPASSWD" > /etc/nginx/.htpasswd
  echo 'auth_basic "Restricted"; auth_basic_user_file /etc/nginx/.htpasswd;' > "$AUTH_CONF"
else
  echo '# basic auth disabled (BASIC_AUTH_HTPASSWD not set)' > "$AUTH_CONF"
fi
