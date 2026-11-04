FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HIVELENS_HOST=0.0.0.0 \
    HIVELENS_REQUIRE_AUTH=1 \
    HIVELENS_SECURE_COOKIES=1 \
    HIVELENS_OPEN_BROWSER=0 \
    HIVELENS_DATA_DIR=/data
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY server.py ./
COPY hivelens/ ./hivelens/
COPY scripts/ ./scripts/
COPY data/demo_assets/ ./data/demo_assets/
COPY data/eval/varroa_eval.json ./data/eval/varroa_eval.json
COPY LICENSE README.md ./
COPY docs/ ./docs/
EXPOSE 8080
CMD ["python", "server.py"]
