FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/apps/server

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential curl \
  && rm -rf /var/lib/apt/lists/*

COPY apps/server/pyproject.toml apps/server/uv.lock apps/server/README.md ./
COPY apps/server/app ./app

RUN pip install --no-cache-dir -i https://mirrors.tencent.com/pypi/simple/ --trusted-host mirrors.tencent.com .

RUN mkdir -p /app/storage/uploads /app/storage/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
