FROM node:22-bookworm-slim AS web-builder
WORKDIR /build/web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM rust:1.88-bookworm AS server-builder
WORKDIR /build
COPY server/Cargo.toml server/Cargo.lock ./server/
COPY server/src ./server/src
COPY vendor/TriviumDB ./vendor/TriviumDB
RUN cargo build --release --manifest-path server/Cargo.toml

FROM python:3.11-slim-bookworm
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir -r /app/worker/requirements.txt
COPY worker/app /app/worker/app
COPY --from=web-builder /build/web/dist /app/web/dist
COPY --from=server-builder /build/server/target/release/shore-memory-server /app/shore-memory-server
COPY scripts/container-start.sh /app/container-start.sh
RUN chmod +x /app/container-start.sh /app/shore-memory-server \
    && mkdir -p /data
ENV PORT=8080
ENV PMS_HOST=0.0.0.0
ENV PMS_DATA_DIR=/data
ENV PMS_WEB_DIST=/app/web/dist
ENV PMW_HOST=127.0.0.1
ENV PMW_PORT=7812
EXPOSE 8080
CMD ["/app/container-start.sh"]
