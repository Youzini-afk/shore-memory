# Stage 1: Build Frontend
FROM node:20 AS frontend-builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Build Backend
FROM node:20 AS backend-builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npx tsc -p electron/tsconfig.json

# Stage 3: Runtime
FROM node:20-slim

# Install Python 3 and basic tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package.json and install production dependencies
COPY package.json package-lock.json ./
RUN npm install --omit=dev

# Copy built artifacts
COPY --from=frontend-builder /app/dist ./dist
COPY --from=backend-builder /app/dist-electron ./dist-electron

# Copy Backend Source
COPY backend ./backend

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
# Use --break-system-packages to allow installing to system python in newer Debian/Ubuntu
RUN pip3 install --no-cache-dir -r backend/requirements.txt --break-system-packages || echo "Warning: Some dependencies failed to install"

# Expose WebBridge Port
EXPOSE 9000

# Set Environment Variables
ENV NODE_ENV=production
ENV PORT=9000
ENV HEADLESS=true

# Start CLI
CMD ["node", "dist-electron/cli/index.js", "--port", "9000"]
