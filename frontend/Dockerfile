# syntax=docker/dockerfile:1
#
# Frontend container for customer-support-agent (sad.md §5: "single-service
# local/dev target for MVP demo"). Two stages: build the static Vite
# bundle with Node, then serve it with a minimal static server — the built
# image ships no Node runtime, only the compiled `dist/` output.

FROM node:22.12.0-bookworm-slim AS build
WORKDIR /app

# Dependency layer first for build-cache efficiency.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Vite inlines every VITE_-prefixed env var into the built JS bundle at
# BUILD time — it is NOT read at container runtime, unlike the backend's
# env vars. sad.md doesn't pin this value; frontend/.env.example already
# documents VITE_API_BASE_URL for local dev. Passed as a build ARG so
# docker-compose.yml (or an operator running `docker build` directly) can
# set it without editing this file. Defaults to the local-dev backend URL
# used throughout setup.md.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27.3-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
# SPA fallback: React Router's BrowserRouter (/chat, /inbox, /ops) needs
# every path to resolve to index.html client-side, not a raw nginx 404.
# Templated (not a static conf) so nginx listens on whatever $PORT the
# platform assigns at runtime — see nginx.conf.template's own comment.
# The image's docker-entrypoint runs envsubst on this before nginx starts.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Fallback only — Railway injects its own PORT per deployment/instance,
# which overrides this at container runtime. Needed so `docker run`/
# docker-compose (which don't set PORT) still resolve the template.
ENV PORT=80

EXPOSE 80

# Not sad.md §5's `/health` requirement — that contract belongs to the
# backend API. This just confirms the static file server itself answers,
# for docker-compose's own `depends_on: condition: service_healthy`
# ordering between the two containers. Shell form (no brackets) so $PORT
# expands to whatever the template above actually bound to.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:${PORT}/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
