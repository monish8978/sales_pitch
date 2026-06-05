FROM python:3.10-slim

# Set environment variable to prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Install system dependencies (build-essential is useful for some python binary builds)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt /workspace/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /workspace/

# Expose port for FastAPI
EXPOSE 1010
