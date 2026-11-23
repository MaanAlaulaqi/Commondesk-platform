ARG MT_BUILD_TRANSLATOR=1
FROM python:3.12-slim AS translator-assets
ARG MT_BUILD_TRANSLATOR
WORKDIR /assets
COPY translator/control.json translator/fetch_control.py ./
RUN mkdir -p /models/translation && if [ "$MT_BUILD_TRANSLATOR" = 1 ]; then python fetch_control.py; fi

# The provider does not support bind or secret mounts in its Dockerfile builder.
# These expiring single-object grants exist only in an intermediate private build layer.
COPY translator/coached-ar-en.json translator/fetch_coached.py ./
COPY translator/coached-build/ /grants/
RUN mkdir -p /models/translation-ar-en && if [ "$MT_BUILD_TRANSLATOR" = 1 ] && [ -f /grants/downloads.json ]; then python fetch_coached.py; fi

FROM python:3.12-slim
ARG MT_BUILD_TRANSLATOR
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODEL_DIR=/models OMP_NUM_THREADS=2 TORCH_NUM_THREADS=2 PORT=8001
COPY worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.1 torchvision==0.24.1 && pip install --no-cache-dir -r /tmp/worker-requirements.txt
COPY worker/encoders.py worker/model-pins.json /app/worker/
RUN python -m worker.encoders && rm -rf /root/.cache/huggingface
COPY translator/requirements.txt /app/translator/requirements.txt
RUN if [ "$MT_BUILD_TRANSLATOR" = 1 ]; then python -m venv /opt/translator && /opt/translator/bin/pip install --no-cache-dir -r /app/translator/requirements.txt; fi
COPY --from=translator-assets /models/translation /models/translation
COPY --from=translator-assets /models/translation-ar-en /models/translation-ar-en
COPY translator/runtime.py translator/control.json translator/observation-policy.json translator/coached-ar-en.json translator/coached-ar-en-policy.json /app/translator/
COPY worker/ /app/worker/
ENV MT_RUNTIME_DIR=/app/translator MT_PYTHON=/opt/translator/bin/python MT_MODEL_DIR=/models/translation MT_MODEL_MANIFEST=/app/translator/control.json MT_DIRECTION_POLICY=/app/translator/observation-policy.json
CMD ["python", "-m", "worker.server"]
