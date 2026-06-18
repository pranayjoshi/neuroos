# NeuroOS Data Generator — Job 01
# Implemented by the Data Generator agent. This is a stub.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
COPY config/ ./config/
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "data_generator", "--help"]
