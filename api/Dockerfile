FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py templates.json ./
RUN useradd --create-home app && mkdir /app/data && chown app /app/data
USER app
CMD ["sh","-c","exec uvicorn main:app --no-access-log --host 0.0.0.0 --port ${PORT:-8000}"]
