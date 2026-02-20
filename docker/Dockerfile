# Synapse Agent - Docker Image
# Protocol Version: 1.0
# Spec Version: 3.1

FROM python:3.11-slim

# Labels for protocol version
LABEL org.synapse.protocol_version="1.0"
LABEL org.synapse.spec_version="3.1"
LABEL org.synapse.version="3.1.0"
LABEL org.synapse.description="Universal Autonomous Agent Platform"

# Security: Create non-root user
RUN groupadd -r synapse && useradd -r -g synapse synapse

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     curl     && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=synapse:synapse synapse/ ./synapse/
COPY --chown=synapse:synapse config/ ./config/
COPY --chown=synapse:synapse skills/ ./skills/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PROTOCOL_VERSION=1.0
ENV SPEC_VERSION=3.1
ENV MODE=docker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3     CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER synapse

# Expose ports
EXPOSE 8000 9090

# Entry point
ENTRYPOINT ["python", "-m", "synapse.main"]
CMD ["--mode", "docker"]
