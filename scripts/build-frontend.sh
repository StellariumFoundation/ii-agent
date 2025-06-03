#!/bin/bash
set -e

echo "Building frontend assets..."

# Navigate to the frontend directory
# Get the directory of the script itself
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/frontend" || exit 1

echo "Installing frontend dependencies..."
yarn install --frozen-lockfile

echo "Running Next.js build..."
yarn build

echo "Navigating back to project root..."
cd "$PROJECT_ROOT" || exit 1

echo "Frontend assets built successfully."
