FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPYCACHEPREFIX=/tmp/codex_pycache
ENV SSELL1_NONINTERACTIVE=1
ENV MPLBACKEND=Agg

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY azure_scheduled_jobs/requirements-azure.txt /tmp/requirements-azure.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-azure.txt

COPY . /app
RUN chmod +x /app/azure_scheduled_jobs/scripts/run_tb11_job.sh

ENTRYPOINT ["/app/azure_scheduled_jobs/scripts/run_tb11_job.sh"]
CMD ["phase1"]
