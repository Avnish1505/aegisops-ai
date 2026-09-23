# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AEGISOPS_DATABASE_URL=sqlite:////app/data/aegisops.db

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and the retrieval corpus the LLM engine reads at startup
COPY aegisops ./aegisops
COPY backend ./backend
COPY knowledge ./knowledge

# Create a non-root user
RUN useradd --create-home --uid 10001 appuser
# Create a directory for the SQLite database and ensure it's writable
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Apply migrations to the database named by AEGISOPS_DATABASE_URL, then serve
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
