#!/bin/bash
set -e

echo "Setting up backend..."

# Ensure the workspace directory exists
DEFAULT_WORKSPACE_PATH="./workspace_local" # Aligning with server run documentation
EFFECTIVE_WORKSPACE_PATH="${WORKSPACE_PATH:-$DEFAULT_WORKSPACE_PATH}"

echo "Ensuring backend workspace directory exists at $EFFECTIVE_WORKSPACE_PATH..."
mkdir -p "$EFFECTIVE_WORKSPACE_PATH"

# Placeholder for other backend setup tasks (e.g., downloading models, setting up databases)
# For now, just confirming workspace creation is the main task.

echo "Backend setup complete. Workspace at $EFFECTIVE_WORKSPACE_PATH"
