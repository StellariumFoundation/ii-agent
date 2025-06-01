#!/bin/bash
# build_desktop.sh
# Script to build the self-contained II-Agent Desktop application.

echo "II-Agent Desktop Build Script"
echo "============================="
echo "Prerequisites:"
echo "1. Python environment with PyInstaller installed (pip install pyinstaller)."
echo "2. All Python dependencies from requirements.txt installed in the environment."
echo "3. Neutralinojs CLI installed (npm install -g @neutralinojs/neu)."
echo "4. Node.js and npm/yarn for Neutralinojs if any JS dependencies are managed via package.json (not currently the case for the minimal template)."
echo "============================="
echo ""

# Exit immediately if a command exits with a non-zero status.
set -e

# Define Paths
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PY_BACKEND_SPEC_FILE="ii_agent_backend.spec"
PY_BACKEND_DIST_DIR="$PROJECT_ROOT/dist" # Default PyInstaller output
PY_BACKEND_OUTPUT_NAME="ii_agent_core_service" # Must match 'name' in COLLECT in the .spec file
NEUTRINO_APP_DIR="$PROJECT_ROOT/ii_agent_desktop"
NEUTRINO_BIN_TARGET_DIR="$NEUTRINO_APP_DIR/app/bin" # Target for Python executable within Neutralino resources

echo "Project Root: $PROJECT_ROOT"
echo "Neutralino App Dir: $NEUTRINO_APP_DIR"
echo "Python Backend Output Name: $PY_BACKEND_OUTPUT_NAME"
echo "Neutralino Binary Target Dir: $NEUTRINO_BIN_TARGET_DIR"
echo ""

# Step 1: Build the Python Backend with PyInstaller
echo "Building Python backend with PyInstaller..."
cd "$PROJECT_ROOT"
if [ ! -f "$PY_BACKEND_SPEC_FILE" ]; then
    echo "ERROR: PyInstaller spec file '$PY_BACKEND_SPEC_FILE' not found in $PROJECT_ROOT!"
    exit 1
fi

# Clean previous PyInstaller builds (optional, but good practice)
echo "Cleaning previous PyInstaller build directories (build/ and dist/$PY_BACKEND_OUTPUT_NAME)..."
rm -rf "$PROJECT_ROOT/build/$PY_BACKEND_OUTPUT_NAME" # PyInstaller's build working directory for this app
rm -rf "$PY_BACKEND_DIST_DIR/$PY_BACKEND_OUTPUT_NAME" # PyInstaller's dist output for this app

# PyInstaller command
pyinstaller "$PY_BACKEND_SPEC_FILE"

PYINSTALLER_EXIT_CODE=$?
if [ $PYINSTALLER_EXIT_CODE -ne 0 ]; then
    echo "ERROR: PyInstaller build failed with exit code $PYINSTALLER_EXIT_CODE."
    exit $PYINSTALLER_EXIT_CODE
fi
echo "Python backend build successful."
echo ""

# Step 2: Copy Python backend executable to Neutralinojs app resources
echo "Copying Python backend to Neutralinojs app resources..."
# Create the target bin directory in Neutralino app if it doesn't exist
mkdir -p "$NEUTRINO_BIN_TARGET_DIR"

# The spec file is configured for a one-folder (onedir) build.
# The output will be in $PY_BACKEND_DIST_DIR/$PY_BACKEND_OUTPUT_NAME/
PY_BACKEND_SOURCE_PATH="$PY_BACKEND_DIST_DIR/$PY_BACKEND_OUTPUT_NAME"

if [ ! -d "$PY_BACKEND_SOURCE_PATH" ]; then
    echo "ERROR: PyInstaller output directory '$PY_BACKEND_SOURCE_PATH' not found!"
    echo "Check your PyInstaller spec file ('name' in COLLECT) and build output."
    exit 1
fi

# Copy the entire folder for onedir builds
# The target within Neutralino's bin will also be a folder.
# Neutralino's spawnProcess will then target executable inside this folder.
# e.g. ./bin/ii_agent_core_service/ii_agent_core_service (Linux/Mac) or ./bin/ii_agent_core_service/ii_agent_core_service.exe (Windows)
NEUTRINO_PYTHON_EXEC_CONTAINER_PATH="$NEUTRINO_BIN_TARGET_DIR/$PY_BACKEND_OUTPUT_NAME"
echo "Removing existing backend in Neutralino app (if any): $NEUTRINO_PYTHON_EXEC_CONTAINER_PATH"
rm -rf "$NEUTRINO_PYTHON_EXEC_CONTAINER_PATH"
echo "Copying from $PY_BACKEND_SOURCE_PATH to $NEUTRINO_PYTHON_EXEC_CONTAINER_PATH..."
# Ensure the parent directory exists for cp -R source_dir dest_dir/ (where dest_dir is NEUTRINO_BIN_TARGET_DIR)
# cp -R source_folder dest_folder/ (if dest_folder exists, it copies source_folder inside it)
# cp -R source_folder dest_folder (if dest_folder does not exist, it creates it and copies content)
# To be safe, we copy into the parent, ensuring the PY_BACKEND_OUTPUT_NAME folder is created at the destination.
cp -R "$PY_BACKEND_SOURCE_PATH" "$NEUTRINO_BIN_TARGET_DIR/"
# This will create $NEUTRINO_BIN_TARGET_DIR/$PY_BACKEND_OUTPUT_NAME

# Verify copy
if [ ! -d "$NEUTRINO_PYTHON_EXEC_CONTAINER_PATH" ]; then # Check if the directory exists
    echo "ERROR: Failed to copy Python backend to $NEUTRINO_PYTHON_EXEC_CONTAINER_PATH"
    exit 1
fi
echo "Python backend successfully copied to Neutralinojs resources."
echo ""

# Step 3: Build the Neutralinojs Application
echo "Building Neutralinojs application..."
cd "$NEUTRINO_APP_DIR"
# Assuming neu CLI is in PATH
neu build --release

NEUTRINO_BUILD_EXIT_CODE=$?
if [ $NEUTRINO_BUILD_EXIT_CODE -ne 0 ]; then
    echo "ERROR: Neutralinojs build failed with exit code $NEUTRINO_BUILD_EXIT_CODE."
    exit $NEUTRINO_BUILD_EXIT_CODE
fi
echo "Neutralinojs application build successful."
echo ""

echo "============================================================"
echo "Self-contained II-Agent Desktop App build process completed!"
echo "You can find the Neutralinojs distributables in:"
echo "$NEUTRINO_APP_DIR/dist"
echo "The Python backend was bundled from: $PY_BACKEND_SOURCE_PATH"
echo "And copied into the Neutralino app at: $NEUTRINO_PYTHON_EXEC_CONTAINER_PATH"
echo "============================================================"

exit 0
