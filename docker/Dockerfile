FROM python:3.12.12-slim
WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY sql ./sql
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps .
COPY data/sample ./data/sample
RUN useradd --create-home appuser && mkdir -p output && chown -R appuser:appuser /app
USER appuser
ENTRYPOINT ["python", "-m", "retaillens"]
CMD ["demo", "--mode", "synthetic", "--output", "/app/output/synthetic"]
