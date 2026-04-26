# syntax=docker/dockerfile:1.7
#
# Multi-stage build:
#   1. node-alpine builds the Vite production bundle.
#   2. nginx-alpine serves the bundle and reverse-proxies /api to the
#      backend service inside the compose network.
#
# Build context for this Dockerfile is the repo root (so we can also
# reach nginx/pyweb.docker.conf), set in docker-compose.yml.

FROM node:24-alpine AS builder
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build


FROM nginx:1.27-alpine

# Replace the stock site with the pyweb config; keep nginx.conf as-is.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx/pyweb.docker.conf /etc/nginx/conf.d/pyweb.conf

# Static bundle from the builder stage.
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

# nginx:alpine's default CMD already runs `nginx -g 'daemon off;'`.
