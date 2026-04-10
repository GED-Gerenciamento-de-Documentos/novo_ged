FROM python:3.11-slim-bookworm

# Instalar dependências do sistema para Oracle (Instant Client) e JBIG2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libffi-dev \
    curl \
    jbig2dec \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    # Oracle Instant Client dependencies
    libaio1 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar Oracle Instant Client Basic Light (para oracledb thick mode) no Linux
RUN mkdir -p /opt/oracle && \
    wget -q https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linuxx64.zip -P /tmp/ && \
    unzip /tmp/instantclient-basiclite-linuxx64.zip -d /opt/oracle && \
    mv /opt/oracle/instantclient*/* /opt/oracle/ && \
    rm -rf /opt/oracle/instantclient* /tmp/instantclient-basiclite-linuxx64.zip && \
    echo /opt/oracle > /etc/ld.so.conf.d/oracle.conf && \
    ldconfig

ENV LD_LIBRARY_PATH="/opt/oracle"

WORKDIR /app

# Copiar arquivos de dependência primeiro (cache de layers)
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Instalar pip e dependências do projeto
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Criar usuário não-root para segurança
RUN useradd -m -u 1000 geduser && chown -R geduser:geduser /app
USER geduser

# Expor porta da API
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicialização
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
