FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COLLECTOR_DATA_ROOT=/data \
    COLLECTOR_CONFIG=/app/zerodha_equity_collector/config/l2_collector_config.azure.json

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip

COPY requirements.txt /app/zerodha_equity_collector/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/zerodha_equity_collector/requirements.txt

COPY . /app/zerodha_equity_collector

RUN chmod +x /app/zerodha_equity_collector/entrypoint_azure.sh

RUN python -m compileall -q /app/zerodha_equity_collector

ENTRYPOINT ["/app/zerodha_equity_collector/entrypoint_azure.sh"]
CMD ["l2-live"]
