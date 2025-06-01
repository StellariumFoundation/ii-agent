#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Building frontend..."
cd frontend
yarn install # Ensure dependencies are up-to-date
yarn build
cd ..

echo "Preparing Neutralinojs resources..."
NEU_APP_DIR="desktop/ii-desktop-app" # Correct path
RESOURCES_FRONTEND_DIR="$NEU_APP_DIR/resources/frontend"

if [ -d "$RESOURCES_FRONTEND_DIR" ]; then
  echo "Removing old frontend build from Neutralinojs resources..."
  rm -rf "$RESOURCES_FRONTEND_DIR"/*
else
  echo "Creating Neutralinojs frontend resource directory..."
  mkdir -p "$RESOURCES_FRONTEND_DIR"
fi

echo "Copying new frontend build to Neutralinojs resources..."
cp -r frontend/out/* "$RESOURCES_FRONTEND_DIR/"

echo "Building Neutralinojs desktop application..."
cd "$NEU_APP_DIR"
neu build --release

echo "Desktop application build complete."
echo "Binaries can be found in $NEU_APP_DIR/dist/"
