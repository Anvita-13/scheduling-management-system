# syntax=docker/dockerfile:1

# ---- build the static assets ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# The production build calls the API at the relative path /api (see src/api/client.js), which nginx.conf
# below proxies to the backend container — so no VITE_API_URL / VITE_BACKEND_URL is needed at build time.
RUN npm run build

# ---- serve them ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=10s \
    CMD wget -qO- http://127.0.0.1/ > /dev/null 2>&1 || exit 1
