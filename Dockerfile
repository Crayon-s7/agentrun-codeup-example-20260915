FROM agentrun-prod-acr-1-registry.cn-beijing.cr.aliyuncs.com/agentrun-lab/console-app:base-python312-amd64-20260909@sha256:9c47360a2a0355e2da18516d0b1c2126ec22c195d2185e97347c9d98398c5bef
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY app ./app

USER 10001:10001
EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/health', timeout=2)"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers", "--loop", "asyncio", "--http", "h11", "--lifespan", "off"]
