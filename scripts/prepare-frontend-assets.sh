#!/bin/bash
set -e

echo "Preparing frontend assets for the Python server..."

# Ensure the script is run from the project root
if [ ! -f "pyproject.toml" ] || [ ! -d "frontend" ]; then
  echo "ERROR: This script must be run from the project root directory."
  echo "Project root should contain 'pyproject.toml' and the 'frontend' directory."
  exit 1
fi

# Clean and create the frontend_build directory
echo "Cleaning and creating frontend_build directory..."
if [ -d "frontend_build" ]; then
  rm -rf frontend_build/*
else
  mkdir frontend_build
fi
mkdir -p frontend_build/.next # Ensure .next subdirectory exists

# Check if source frontend build artifacts exist
if [ ! -d "frontend/.next/static" ]; then
    echo "ERROR: Source 'frontend/.next/static' directory not found. Please build the frontend first (e.g., using scripts/build-frontend.sh)."
    exit 1
fi
if [ ! -d "frontend/public" ]; then
    echo "ERROR: Source 'frontend/public' directory not found."
    exit 1
fi
if [ ! -f "frontend/.next/server/app/index.html" ]; then
    echo "ERROR: Source 'frontend/.next/server/app/index.html' not found. Please build the frontend first."
    exit 1
fi


# Copy Next.js static assets
echo "Copying frontend/.next/static to frontend_build/.next/static..."
cp -R frontend/.next/static frontend_build/.next/

# Copy public assets
echo "Copying frontend/public to frontend_build/public..."
cp -R frontend/public frontend_build/

# Copy the main application HTML file
echo "Copying frontend/.next/server/app/index.html to frontend_build/index.html..."
cp frontend/.next/server/app/index.html frontend_build/index.html

echo "Frontend assets prepared successfully in frontend_build/."
