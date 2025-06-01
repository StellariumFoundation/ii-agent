#!/bin/bash
# build_desktop.sh - Updated
# Script to build the self-contained II-Agent Desktop application with React frontend.

echo "II-Agent Desktop Build Script (with React Frontend)"
echo "===================================================" # Corrected title for consistency
echo "Prerequisites:"
echo "1. Python environment with PyInstaller installed (pip install pyinstaller)."
echo "2. All Python dependencies from requirements.txt installed in the environment."
echo "3. Neutralinojs CLI installed (npm install -g @neutralinojs/neu)."
echo "4. Node.js and npm (or yarn) for building the React frontend."
echo "==================================================="
echo ""

# Exit immediately if a command exits with a non-zero status.
set -e

# Define Paths
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Python backend paths
PY_BACKEND_SPEC_FILE="ii_agent_backend.spec"
PY_BACKEND_DIST_DIR="$PROJECT_ROOT/dist"
PY_BACKEND_OUTPUT_NAME="ii_agent_core_service" # Must match 'name' in COLLECT in the .spec file
# React frontend paths
REACT_APP_DIR="$PROJECT_ROOT/frontend"
REACT_BUILD_OUTPUT_DIR="$REACT_APP_DIR/build" # Common for Create React App; adjust if Next.js outputs to .next/static or similar after export
# Neutralino app paths
NEUTRINO_APP_DIR="$PROJECT_ROOT/ii_agent_desktop"
NEUTRINO_APP_CONTENT_DIR="$NEUTRINO_APP_DIR/app"
NEUTRINO_APP_JS_DIR="$NEUTRINO_APP_CONTENT_DIR/js"     # Target for app_bootstrap.js, e.g., app/js/
NEUTRINO_PYTHON_BIN_DIR="$NEUTRINO_APP_CONTENT_DIR/bin"
NEUTRINO_PYTHON_EXEC_TARGET_DIR="$NEUTRINO_PYTHON_BIN_DIR/$PY_BACKEND_OUTPUT_NAME"

# Source location of our bootstrap script (created in a previous step)
APP_BOOTSTRAP_JS_SOURCE="$PROJECT_ROOT/ii_agent_desktop/app/js/app_bootstrap.js"


echo "Project Root: $PROJECT_ROOT"
echo "React App Dir: $REACT_APP_DIR"
echo "Neutralino App Dir: $NEUTRINO_APP_DIR"
echo "Python Backend Output Name: $PY_BACKEND_OUTPUT_NAME"
echo "Bootstrap JS Source: $APP_BOOTSTRAP_JS_SOURCE"
echo ""


echo "--- Step 1: Building Python Backend ---"
cd "$PROJECT_ROOT"
if [ ! -f "$PY_BACKEND_SPEC_FILE" ]; then echo "ERROR: PyInstaller spec file '$PY_BACKEND_SPEC_FILE' not found!" >&2; exit 1; fi
echo "Cleaning previous Python build directories (build/$PY_BACKEND_OUTPUT_NAME, dist/$PY_BACKEND_OUTPUT_NAME)..."
rm -rf "$PROJECT_ROOT/build/$PY_BACKEND_OUTPUT_NAME"
rm -rf "$PY_BACKEND_DIST_DIR/$PY_BACKEND_OUTPUT_NAME"
pyinstaller "$PY_BACKEND_SPEC_FILE"
if [ $? -ne 0 ]; then echo "ERROR: PyInstaller build failed." >&2; exit 1; fi
echo "Python backend build successful."
echo ""

echo "--- Step 2: Building React Frontend ---"
cd "$REACT_APP_DIR"
if [ ! -f "package.json" ]; then echo "ERROR: package.json not found in $REACT_APP_DIR!" >&2; exit 1; fi
echo "Installing React frontend dependencies (npm or yarn)..."
if [ -f "yarn.lock" ]; then
    yarn install --frozen-lockfile
else
    npm install --legacy-peer-deps
fi
if [ $? -ne 0 ]; then echo "ERROR: React npm/yarn install failed." >&2; exit 1; fi

echo "Building React frontend (npm run build or export)..."
if npm run build --if-present; then
    echo "React build script 'build' successful. Output expected in $REACT_BUILD_OUTPUT_DIR."
elif npm run export --if-present; then
    echo "React build script 'export' successful."
    if [ -d "$REACT_APP_DIR/out" ]; then
        REACT_BUILD_OUTPUT_DIR="$REACT_APP_DIR/out"
        echo "Next.js export detected, using $REACT_BUILD_OUTPUT_DIR as source."
    fi
else
    echo "ERROR: Neither 'npm run build' nor 'npm run export' succeeded for React app." >&2
    exit 1
fi
if [ ! -d "$REACT_BUILD_OUTPUT_DIR" ]; then echo "ERROR: React build output dir '$REACT_BUILD_OUTPUT_DIR' not found!" >&2; exit 1; fi
echo "React frontend build successful."
cd "$PROJECT_ROOT"
echo ""

echo "--- Step 3: Preparing Neutralinojs 'app' Content Directory ---"
# Ensure target directories within app/ exist
mkdir -p "$NEUTRINO_PYTHON_BIN_DIR" # app/bin/
mkdir -p "$NEUTRINO_APP_JS_DIR"     # app/js/

echo "Cleaning Neutralino app content directory ($NEUTRINO_APP_CONTENT_DIR), preserving 'bin/'..."
shopt -s extglob
cd "$NEUTRINO_APP_CONTENT_DIR"
rm -rf !(bin) # Deletes everything in app/ except the 'bin' folder. This means app/js is deleted if it existed.
cd "$PROJECT_ROOT"
shopt -u extglob
# Re-create app/js after cleaning, because React build might not create it.
mkdir -p "$NEUTRINO_APP_JS_DIR"

echo "Copying React build from $REACT_BUILD_OUTPUT_DIR to $NEUTRINO_APP_CONTENT_DIR/..."
cp -R "$REACT_BUILD_OUTPUT_DIR"/* "$NEUTRINO_APP_CONTENT_DIR/"
echo "React build copied."

echo "Copying app_bootstrap.js to $NEUTRINO_APP_JS_DIR/app_bootstrap.js..."
if [ ! -f "$APP_BOOTSTRAP_JS_SOURCE" ]; then
    echo "ERROR: app_bootstrap.js not found at $APP_BOOTSTRAP_JS_SOURCE! It should have been created in a previous step." >&2
    exit 1
fi
cp "$APP_BOOTSTRAP_JS_SOURCE" "$NEUTRINO_APP_JS_DIR/app_bootstrap.js"
echo "app_bootstrap.js copied."
# Note: neutralino.js is handled after 'neu update' in a later step.
echo ""

echo "--- Step 4: Copying Python Backend to Neutralinojs App ---"
PY_BACKEND_SOURCE_PATH="$PY_BACKEND_DIST_DIR/$PY_BACKEND_OUTPUT_NAME"
if [ ! -d "$PY_BACKEND_SOURCE_PATH" ]; then echo "ERROR: PyInstaller output dir '$PY_BACKEND_SOURCE_PATH' not found!" >&2; exit 1; fi

# NEUTRINO_PYTHON_EXEC_TARGET_DIR is app/bin/ii_agent_core_service
mkdir -p "$NEUTRINO_PYTHON_EXEC_TARGET_DIR" # Ensure this specific folder exists
echo "Copying Python backend from $PY_BACKEND_SOURCE_PATH/* to $NEUTRINO_PYTHON_EXEC_TARGET_DIR/..."
rsync -a --delete "$PY_BACKEND_SOURCE_PATH/" "$NEUTRINO_PYTHON_EXEC_TARGET_DIR/"

PYTHON_EXEC_IN_NEUTRINO_BASE="$NEUTRINO_PYTHON_EXEC_TARGET_DIR/$PY_BACKEND_OUTPUT_NAME"
if [ ! -f "$PYTHON_EXEC_IN_NEUTRINO_BASE" ] && [ ! -f "$PYTHON_EXEC_IN_NEUTRINO_BASE.exe" ]; then
    echo "ERROR: Failed to copy Python executable '$PY_BACKEND_OUTPUT_NAME' to $NEUTRINO_PYTHON_EXEC_TARGET_DIR" >&2
    exit 1
fi
echo "Python backend copied."
echo ""

echo "--- Step 5: Building Neutralinojs Application ---"
cd "$NEUTRINO_APP_DIR"
echo "Running 'neu update' to ensure latest client library..."
neu update

NEUTRINO_CLIENT_LIB_UPDATED_SOURCE="$NEUTRINO_APP_DIR/resources/js/neutralino.js"
NEUTRINO_CLIENT_LIB_TARGET_IN_APP="$NEUTRINO_APP_CONTENT_DIR/neutralino.js" # Target is app/neutralino.js

echo "Copying Neutralino client library (neutralino.js) to app root..."
if [ -f "$NEUTRINO_CLIENT_LIB_UPDATED_SOURCE" ]; then
    cp "$NEUTRINO_CLIENT_LIB_UPDATED_SOURCE" "$NEUTRINO_CLIENT_LIB_TARGET_IN_APP"
    echo "Copied neutralino.js to $NEUTRINO_CLIENT_LIB_TARGET_IN_APP."
else
    echo "ERROR: neutralino.js not found in resources/js after 'neu update'. Cannot proceed!" >&2
    exit 1
fi

echo "Running 'neu build --release'..."
neu build --release
if [ $? -ne 0 ]; then echo "ERROR: Neutralinojs build failed." >&2; exit 1; fi
echo "Neutralinojs application build successful."
cd "$PROJECT_ROOT"
echo ""

echo "--- Build Process Completed ---"
echo "Distributables in: $NEUTRINO_APP_DIR/dist"
echo "Python backend was bundled from: $PY_BACKEND_SOURCE_PATH and copied into $NEUTRINO_PYTHON_EXEC_TARGET_DIR"
echo "React frontend was built from: $REACT_APP_DIR (output: $REACT_BUILD_OUTPUT_DIR) and copied into $NEUTRINO_APP_CONTENT_DIR"
echo "Bootstrap JS ($APP_BOOTSTRAP_JS_SOURCE) copied to: $NEUTRINO_APP_JS_DIR/app_bootstrap.js"
echo "Neutralino Client (neutralino.js) copied to: $NEUTRINO_CLIENT_LIB_TARGET_IN_APP"
echo "============================="
exit 0
