FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN chown -R appuser:appuser /app

USER appuser

ENV PORT=5001 \
    CHECKPOINT_DB_PATH=/data/checkpoints.db \
    RUN_CONTEXT=APP

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import os,socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', int(os.environ.get('PORT','5001')))); s.close()"

CMD ["python", "app.py"]
