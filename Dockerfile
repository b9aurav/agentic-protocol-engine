# Multi-stage build for APE CLI distribution
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src/ ./src/
COPY config/ ./config/
COPY docker/ ./docker/
COPY services/ ./services/

# Build the application
RUN npm run build

# Production stage
FROM node:18-alpine AS production

# Install Docker CLI for container orchestration
RUN apk add --no-cache docker-cli docker-compose

# Create app user
RUN addgroup -g 1001 -S ape && \
    adduser -S ape -u 1001

# Set working directory
WORKDIR /app

# Copy built application
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
COPY --from=builder /app/config ./config
COPY --from=builder /app/docker ./docker
COPY --from=builder /app/services ./services

# Change ownership
RUN chown -R ape:ape /app

# Switch to app user
USER ape

# Expose default ports (if needed for development)
EXPOSE 3000 8080 9090

# Set entrypoint
ENTRYPOINT ["node", "dist/cli.js"]
CMD ["--help"]

# Labels for metadata
LABEL org.opencontainers.image.title="Agentic Protocol Engine"
LABEL org.opencontainers.image.description="AI-driven load testing tool using intelligent LLM agents"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/b9aurav/agentic-protocol-engine"