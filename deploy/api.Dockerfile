# Session API for local runs (docker compose --profile site). No data, caches or model weights in the image: the
# private search model and the cost ledger are mounted at run time, secrets come from .env.
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY src ./src
# editable: radlabel.api.sample finds data/sample/ relative to the source tree
RUN pip install --no-cache-dir -e ".[embed]"
COPY data/sample ./data/sample
RUN useradd --create-home app && mkdir -p artifacts/llm_cache && chown app artifacts/llm_cache
USER app
RUN mkdir -p /home/app/.cache/huggingface
EXPOSE 8000
HEALTHCHECK --interval=10s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "radlabel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
