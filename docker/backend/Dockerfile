# Stage 1: Frontend Builder
FROM node:18-alpine AS frontend-builder

WORKDIR /build_root # Represents a simulated project root for the build script

# Copy frontend source code
COPY frontend ./frontend

# Copy the build script
COPY scripts/build-frontend.sh ./scripts/build-frontend.sh
RUN chmod +x ./scripts/build-frontend.sh

# Run the build script (it handles yarn install and yarn build internally)
# The script changes directory to ./frontend and then comes back.
RUN ./scripts/build-frontend.sh
# Built assets are now in /build_root/frontend/.next and /build_root/frontend/public

# Stage 2: Python Application Builder (for Python dependencies)
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
    && pip install --no-cache-dir . # Installs the project itself and its dependencies

# Stage 3: Final Python Application Stage
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

# Copy virtual environment from Python builder stage
COPY --from=final-app-builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy utility scripts
COPY scripts/prepare-frontend-assets.sh /app/scripts/prepare-frontend-assets.sh
COPY scripts/setup-backend.sh /app/scripts/setup-backend.sh
RUN chmod +x /app/scripts/*.sh

# Create the directory structure that prepare-frontend-assets.sh expects to read from
# This is a temporary staging area within this final stage for assets from frontend-builder
RUN mkdir -p /app/frontend/.next/server/app
RUN mkdir -p /app/frontend/public

# Copy built frontend assets from the frontend-builder stage into the temporary location
# that prepare-frontend-assets.sh will use as a source.
# Source paths are relative to /build_root in the frontend-builder stage.
# Destination paths are relative to /app in this stage.
COPY --from=frontend-builder /build_root/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /build_root/frontend/public /app/frontend/public
COPY --from=frontend-builder /build_root/frontend/.next/server/app/index.html /app/frontend/.next/server/app/index.html

# Run the script to move assets to the final /app/frontend_build location
RUN /app/scripts/prepare-frontend-assets.sh
# This script creates /app/frontend_build and populates it.

# Copy backend application code (including ws_server.py, etc.)
# This must come AFTER frontend asset preparation if frontend_build is at /app/frontend_build
# and COPY . . would overwrite it or its contents if not handled carefully.
# prepare-frontend-assets.sh creates frontend_build, so COPY . . should be fine.
COPY . .

# Run backend setup script (currently minimal, e.g. ensures workspace dir)
# WORKSPACE_PATH env var will be used by this script if set at runtime, otherwise defaults.
RUN /app/scripts/setup-backend.sh
# Note: The setup-backend.sh script creates a workspace directory (e.g. /app/workspace_local_setup or $WORKSPACE_PATH)
# The main application uses WORKSPACE_PATH (e.g. /app/workspace from docker-compose.yaml)

# Install Playwright in a single layer
RUN playwright install --with-deps chromium

# Set environment variables
ENV PYTHONUNBUFFERED=1

COPY docker/backend/run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Expose port for WebSocket server
EXPOSE 8000

ENTRYPOINT ["/app/run.sh"]