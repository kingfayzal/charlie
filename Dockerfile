# PrimeOps Agentic OS — Cloud Run Container
# Multi-stage build for minimal image size

FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/deps -r requirements.txt

# --- Production Stage ---
FROM python:3.11-slim

# Security: non-root user
RUN groupadd -r primeops && useradd -r -g primeops primeops

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /build/deps /usr/local/lib/python3.11/site-packages/

# Copy application code
COPY app/ ./app/

# Cloud Run expects PORT env var (default 8080)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER primeops

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
