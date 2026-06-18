# NeuroOS DSP Pipeline — Job 02
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ ./src/

CMD ["python", "-m", "dsp_pipeline"]
