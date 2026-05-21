# Synapse Agent - Multi-stage Dockerfile
# Protocol Version: 1.0
# Spec Version: 3.4

# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Runtime - Minimal production image
# ============================================
FROM gcr.io/distroless/python3-debian12 as runtime

# Labels
LABEL org.synapse.protocol_version="1.0"
LABEL org.synapse.spec_version="3.4"
LABEL org.synapse.version="3.4.1"
LABEL org.synapse.description="Universal Autonomous Agent Platform"
LABEL org.opencontainers.image.source="https://github.com/synapse/synapse"
LABEL org.opencontainers.image.description="Distributed Cognitive Platform for Autonomous Agents"
LABEL org.opencontainers.image.licenses="MIT"

# Copy installed packages from builder
COPY --from=builder /root/.local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
WORKDIR /app
COPY --chown=nonroot:nonroot synapse/ ./synapse/
COPY --chown=nonroot:nonroot config/ ./config/
COPY --chown=nonroot:nonroot skills/ ./skills/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PROTOCOL_VERSION=1.0
ENV SPEC_VERSION=3.4
ENV MODE=docker
ENV PATH=/usr/local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["/usr/bin/curl", "-f", "http://localhost:8000/health"] || exit 1

# Non-root user (distroless uses 'nonroot')
USER nonroot

# Expose ports
# 8000 - API
# 8080 - Web UI
# 9090 - Metrics
EXPOSE 8000 8080 9090

# Entry point
ENTRYPOINT ["/usr/bin/python3", "-m", "synapse.main"]
CMD ["--mode", "docker", "--web-ui"]
