FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PREVIEW_NODE_MODULES=/opt/preview/node_modules \
    ESBUILD_BIN=/opt/preview/node_modules/.bin/esbuild

# Node is only used to bundle generated React sources for the live preview.
# Generated projects themselves never run npm install on the server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/preview
COPY runtime/frontend/package.json runtime/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
