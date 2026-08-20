# ---- Stage 1: Build ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Stage 2: Serve ----
FROM nginx:1.27-alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /app/dist /usr/share/nginx/html
# A template (not a static conf) so the backend hostname can differ per
# environment: docker-compose/Kubernetes both resolve the bare service name
# "backend-svc", but ECS Cloud Map only resolves the fully-qualified
# "backend-svc.<namespace>" — the ECS task definition overrides BACKEND_HOST
# to that FQDN. NGINX_ENVSUBST_FILTER restricts substitution to just this
# variable so nginx's own $host/$remote_addr/etc. runtime variables in the
# template are left untouched.
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV BACKEND_HOST=backend-svc
ENV NGINX_ENVSUBST_FILTER=^BACKEND_HOST$
# Opt-in basic auth — see the script for details.
COPY docker-entrypoint.d/50-configure-auth.sh /docker-entrypoint.d/50-configure-auth.sh
RUN chmod +x /docker-entrypoint.d/50-configure-auth.sh
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
