# ── Stage 1: build React app ────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
# Một lần npm install duy nhất (thay cho npm ci + rm -rf + install lại của bản
# cũ): npm install tự bổ sung binding native musl/Alpine còn thiếu trong
# lockfile sinh trên macOS (rolldown/vite). Cache mount giúp rebuild chỉ tải
# package thiếu.
RUN --mount=type=cache,target=/root/.npm \
    npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ── Stage 2: serve bằng Nginx ───────────────────────────────────────────────
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
