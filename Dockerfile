# Python Development Container for claude-quickstarts
# Used for CI/CD and standalone container runs

FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (better layer caching)
COPY pyproject.toml ./
COPY agents/ ./agents/
COPY autonomous-coding/requirements.txt ./autonomous-coding/

# Install Python dependencies
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir pytest pytest-asyncio

# Copy the rest of the application
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Default command runs tests
CMD ["pytest", "agents/tests/", "autonomous-coding/test_security.py", "-v"]
