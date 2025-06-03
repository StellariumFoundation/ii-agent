# Stage 1: Frontend Builder
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend_src

# Copy package.json and yarn.lock
COPY frontend/package.json frontend/yarn.lock ./

# Install frontend dependencies
RUN yarn install --frozen-lockfile

# Copy the rest of the frontend code
COPY frontend/ ./

# Build the frontend
RUN yarn build

# Stage 2: Python Application (Final Stage)
FROM python:3.10-slim AS final-app-builder

# Install build dependencies for Python
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the files needed for Python installation
COPY pyproject.toml .
COPY README.md .
COPY src/ii_agent/ ./src/ii_agent/

# Install Python dependencies into a virtual environment
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    xvfb \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=final-app-builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# Create frontend_build directory for Next.js static assets
RUN mkdir -p /app/frontend_build/.next

# Copy built frontend assets from frontend-builder stage
COPY --from=frontend-builder /app/frontend_src/.next/static /app/frontend_build/.next/static
COPY --from=frontend-builder /app/frontend_src/public /app/frontend_build/public
COPY --from=frontend-builder /app/frontend_src/.next/server/app/index.html /app/frontend_build/index.html

# Copy backend application code (including ws_server.py)
# This must come AFTER copying frontend assets to avoid overwriting frontend_build
COPY . .

# Create workspace directory (if it's not created by COPY .)
RUN mkdir -p workspace

# Install Playwright in a single layer
RUN playwright install --with-deps chromium

# Set environment variables
ENV PYTHONUNBUFFERED=1

COPY docker/backend/run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Expose port for WebSocket server
EXPOSE 8000

ENTRYPOINT ["/app/run.sh"]