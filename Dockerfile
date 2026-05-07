FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Shanghai

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/

COPY main.py ./
COPY api ./api
COPY collector ./collector
COPY providers ./providers
COPY storage ./storage
COPY backfill_projects.py ./
COPY README.md ./
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

ARG BUILD_VERSION=dev
RUN echo "$BUILD_VERSION" > /app/version.txt

EXPOSE 5002

ENV mode=api

CMD ["python", "main.py"]
