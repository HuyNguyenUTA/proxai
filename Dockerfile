FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[standard]" 2>/dev/null || pip install --no-cache-dir \
    fastapi uvicorn[standard] httpx python-dotenv click jinja2 aiofiles

# Copy source
COPY proxai/ ./proxai/

# Data directory for SQLite
RUN mkdir -p /root/.proxai

EXPOSE 8090 8091

ENV PROXAI_HOST=0.0.0.0
ENV PROXAI_PORT=8090
ENV PROXAI_DASHBOARD_PORT=8091
ENV PROXAI_DASHBOARD_ENABLED=true

CMD ["python", "-m", "uvicorn", "proxai.server:app", "--host", "0.0.0.0", "--port", "8090"]
