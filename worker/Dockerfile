FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODEL_DIR=/models OMP_NUM_THREADS=2 TORCH_NUM_THREADS=2 PORT=8001
COPY worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.1 torchvision==0.24.1 && pip install --no-cache-dir -r /tmp/worker-requirements.txt
COPY worker/ /app/worker/
RUN python -m worker.encoders && rm -rf /root/.cache/huggingface
CMD ["python", "-m", "worker.server"]
