# ==========================================
# STAGE 1: Builder
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Instalar dependencias en un virtualenv aislado para exportar
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install .

# ==========================================
# STAGE 2: Runtime Final
# ==========================================
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

# Copiar entorno virtual precompilado
COPY --from=builder /opt/venv /opt/venv

# Crear usuario y grupo no-root para seguridad
RUN groupadd -g 10001 decagroup && \
    useradd -u 10001 -g decagroup -s /bin/bash -m decauser

# Crear directorios para base de datos y almacenamiento de ficheros
RUN mkdir -p /app/instance /app/storage && \
    chown -R decauser:decagroup /app

# Copiar código fuente
COPY --chown=decauser:decagroup src/ /app/src/
COPY --chown=decauser:decagroup pyproject.toml README.md /app/

# Cambiar a usuario no-root
USER decauser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
