# NeuroOS Intent Engine — Job 03
# Implemented by the Intent Engine agent. This is a stub.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir numpy scipy scikit-learn onnxruntime

COPY src/ ./src/

CMD ["python", "-c", "print('Intent Engine stub — see jobs/03_intent_engine/JOB.md')"]
