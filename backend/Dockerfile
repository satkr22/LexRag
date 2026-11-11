# Use the official lightweight Python image
FROM python:3.12-slim

# 1. Set production environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 2. Install essential system dependencies
# --no-install-recommends keeps the image size small by ignoring optional packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# 3. Create a dedicated non-root user for security
RUN groupadd -r appgroup && \
    useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# 4. Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# 5. Copy the rest of your application code
COPY . .

# 6. Transfer ownership of the files to your non-root user
RUN chown -R appuser:appgroup /app

# 7. Switch from root to the new restricted user
USER appuser

# 8. Document the exposed port
EXPOSE 9000

ENTRYPOINT ["./entrypoint.sh"]
# 9. Start the server for production (No --reload, multiple workers)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "4"]