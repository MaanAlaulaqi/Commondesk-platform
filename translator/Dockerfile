FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MT_THREADS=2
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY runtime.py .
USER 65534:65534
CMD ["uvicorn", "runtime:create_app", "--factory", "--host", "0.0.0.0", "--port", "8012", "--no-access-log"]
