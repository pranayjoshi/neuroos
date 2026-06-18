# NeuroOS Data Generator — Job 01
# Implemented by the Data Generator agent. This is a stub.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install numpy scipy click pyyaml

# Copy source
COPY src/ ./src/

CMD ["python", "-m", "data_generator", "--help"]
