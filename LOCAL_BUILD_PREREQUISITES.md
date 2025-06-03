# Local Build and Run Prerequisites

This document outlines the necessary software, tools, and configurations required to build and run this project locally.

## 1. Operating System

*   A Unix-like environment (Linux or macOS) is recommended, as many scripts and commands are tailored for it (e.g., `yarn`, `mkdir`, `cp`).
*   Windows users: You may need to adapt commands or use the Windows Subsystem for Linux (WSL) for a smoother experience.

## 2. Software Versions

*   **Python:**
    *   Version: Python 3.10 or higher is required (as per `pyproject.toml`).
    *   The `.python-version` file in this repository specifies `3.10`, which is the version used for development and testing.
*   **Node.js:**
    *   Version: Node.js v18.x is recommended (based on the version used in previous Docker configurations, e.g., `node:18-alpine`).
*   **Yarn (Package Manager for Node.js):**
    *   Yarn is used for managing frontend dependencies (indicated by the presence of `yarn.lock` in the `frontend` directory).
    *   A recent version of Yarn 1 (Classic) should be compatible.

## 3. Build and Installation Tools

*   **For Python:**
    *   `pip`: For installing Python dependencies from `pyproject.toml`.
    *   `uv`: (Optional, but recommended for speed if available) Can also be used for Python dependency management, as indicated by `uv.lock`.
*   **For Node.js (Frontend):**
    *   `yarn`: For installing frontend dependencies using `yarn install`.
*   **General:**
    *   Standard shell commands like `mkdir`, `cp` are used in various scripts.

## 4. Environment Variables

Several environment variables are critical for the application to run correctly, especially the backend components. It's recommended to create a `.env` file in the project root directory by copying `.env.example` and filling in the necessary values. Alternatively, these variables can be set directly in your shell environment.

Key variables include:

*   **API Keys (from `.env.example`):**
    *   `ANTHROPIC_API_KEY`: Required if using Anthropic models.
    *   `TAVILY_API_KEY`: Required if using the Tavily search tool.
    *   (Alternatively, `SERPAPI_KEY` and `FIRE_CRAWL_KEY` if using those services).
*   **Google Cloud (if using Vertex AI services):**
    *   `GOOGLE_APPLICATION_CREDENTIALS`: Path to your Google Cloud service account JSON key file.
    *   `PROJECT_ID`: Your Google Cloud Project ID.
    *   `REGION`: The Google Cloud region for your services.
*   **Workspace Configuration:**
    *   `WORKSPACE_PATH`: Defines the directory for agent workspaces. For local development, you can set this to a local path, e.g., `WORKSPACE_PATH=./workspace_local`. The `start.sh` script defaults this to `${PWD}/workspace` for Docker.
*   **Frontend (from `.env.example`):**
    *   `STATIC_FILE_BASE_URL`: While the frontend and backend are now served from the same origin, this was present in `.env.example`. For a fully local setup, if any part of the frontend still references this, it would typically be `http://localhost:PORT` where `PORT` is the backend port (e.g., `http://localhost:8000/`).

**Note:** Ensure that the file specified by `GOOGLE_APPLICATION_CREDENTIALS` is accessible by the application, and that the `WORKSPACE_PATH` directory exists.

## 5. Installing Python Dependencies Locally

Follow these steps to set up a Python virtual environment and install the necessary backend dependencies. These commands should be run from the project root directory (where `pyproject.toml` is located).

1.  **Create a Python Virtual Environment:**
    A virtual environment helps manage project-specific dependencies separately from your global Python installation.
    ```bash
    python3 -m venv .venv
    # Or, if 'python3' is not found, try 'python'
    # python -m venv .venv
    ```

2.  **Activate the Virtual Environment:**
    *   For Linux/macOS:
        ```bash
        source .venv/bin/activate
        ```
    *   For Windows (Git Bash or WSL):
        ```bash
        source .venv/Scripts/activate
        ```
    *   For Windows (Command Prompt):
        ```bash
        .venv\Scripts\activate.bat
        ```
    *   For Windows (PowerShell):
        ```bash
        .venv\Scripts\Activate.ps1
        ```
    Your shell prompt should change to indicate that the virtual environment is active (e.g., `(.venv) your-prompt$`).

3.  **Install Dependencies:**
    This project can use `uv` (a fast Python package installer and resolver) or standard `pip`. `uv` is recommended if available. The `-e` flag installs the project in "editable" mode, which is useful for development.

    *   **Using `uv` (Recommended):**
        ```bash
        uv pip install -e .
        ```
    *   **Using `pip` (Alternative):**
        ```bash
        pip install -e .
        ```

4.  **Verification (Optional):**
    To quickly check if a key dependency (like FastAPI) has been installed correctly, you can run:
    ```bash
    python -c "import fastapi; print(f'FastAPI version: {fastapi.__version__}')"
    ```
    This should print the installed version of FastAPI without errors.

After these steps, your Python environment will be ready for running the backend application.

## 6. Building Frontend Assets Locally

These steps describe how to install frontend dependencies and build the static assets required for the user interface.

1.  **Navigate to the Frontend Directory:**
    All frontend commands should be run from the `frontend` subdirectory.
    ```bash
    cd frontend
    ```

2.  **Install Node.js Dependencies:**
    This command installs the necessary packages defined in `frontend/package.json` and `frontend/yarn.lock`.
    ```bash
    yarn install --frozen-lockfile
    ```
    The `--frozen-lockfile` flag ensures that the exact versions specified in `yarn.lock` are used, providing reproducible builds.

3.  **Build Frontend Assets:**
    This command compiles the Next.js application into static HTML, CSS, and JavaScript files. The output is typically placed in the `frontend/.next` directory.
    ```bash
    yarn build
    ```

4.  **Navigate Back to Project Root (Optional):**
    After the build is complete, you can return to the project root directory.
    ```bash
    cd ..
    ```

Once these steps are completed, the static frontend assets will be built. The Python server (`ws_server.py`) is configured to serve these assets from a specific directory (`frontend_build`) at the project root. The next section details how to copy the built assets to this location.

## 7. Preparing Built Frontend Assets for the Python Server

After building the frontend assets (as described in Section 6), you need to copy them to the `frontend_build` directory at the project root. The Python FastAPI server (`ws_server.py`) is configured to serve static files from this location.

Ensure you are in the project root directory before running these commands.

1.  **Create the `frontend_build` Directory Structure:**
    This command creates the necessary target directories. The `-p` flag ensures that parent directories are created if they don't exist.
    ```bash
    mkdir -p frontend_build/.next
    ```

2.  **Copy Next.js Static Assets:**
    This copies the compiled JavaScript, CSS, fonts, and other static chunks generated by the Next.js build process.
    ```bash
    cp -R frontend/.next/static frontend_build/.next/static
    ```

3.  **Copy Public Assets:**
    This copies files from the `frontend/public` directory (e.g., `favicon.ico`, images, manifest files).
    ```bash
    cp -R frontend/public frontend_build/public
    ```

4.  **Copy the Main Application HTML File:**
    This is the main HTML shell for the Next.js application (App Router). The Python server will use this file for client-side routing.
    ```bash
    cp frontend/.next/server/app/index.html frontend_build/index.html
    ```

**Note for Windows Users:** The `cp -R` command is for Unix-like systems. Windows users might need to use alternatives:
*   `robocopy frontend\.next\static frontend_build\.next\static /E`
*   `robocopy frontend\public frontend_build\public /E`
*   `copy frontend\.next\server\app\index.html frontend_build\index.html`
    (Or use `xcopy /E /I` for directories).

After these steps, the `frontend_build` directory will contain all the necessary static assets, and the Python server, when started, should be able to serve the frontend application.

## 8. Running the Python Backend Server Locally

Once all dependencies are installed, frontend assets are built and prepared, and environment variables are set, you can run the Python backend server.

1.  **Ensure You Are in the Project Root Directory:**
    All commands should be run from the project root.

2.  **Activate the Python Virtual Environment:**
    If not already active from previous steps:
    *   Linux/macOS: `source .venv/bin/activate`
    *   Windows: Refer to Section 5 for appropriate activation commands.

3.  **Set Environment Variables:**
    The application relies on environment variables (see Section 4). Ensure these are set. If you haven't created a `.env` file that the application loads, you might need to export them in your current shell session. For `WORKSPACE_PATH`, if it's not set, the application might default or error. For local testing:
    ```bash
    export WORKSPACE_PATH=./workspace_local
    # Ensure this directory exists:
    mkdir -p ./workspace_local
    ```
    Set other critical variables like API keys if they are not in a `.env` file that `python-dotenv` can pick up from `ws_server.py`.

4.  **Run the FastAPI Server:**
    The `ws_server.py` script is designed to be run directly. It parses arguments for host, port, etc.
    ```bash
    python ws_server.py --port 8000
    ```
    You can change the port if needed. The default host is `0.0.0.0`.

    Alternatively, for development, you might use `uvicorn` directly with reload, but for testing the build as per these instructions, running the script is more straightforward:
    ```bash
    # For development with auto-reload (optional):
    # uvicorn ws_server:app --host 0.0.0.0 --port 8000 --reload
    ```

5.  **Server Output:**
    You should see output similar to:
    ```
    INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
    INFO:     Started reloader process [xxxxx] using statreload
    INFO:     Started server process [xxxxx]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    ```
    This indicates the server is running and serving on the specified port. You can then access `http://localhost:8000` in your browser to see the frontend.

## 9. Verifying the Application Locally

After completing all the setup, build, and run steps, verify that the application is working correctly in your web browser.

1.  **Access the Application:**
    Open your web browser and navigate to the address where the Python server is running. This is typically `http://localhost:8000` or `http://127.0.0.1:8000` (if you used port 8000).

2.  **What to Check:**
    *   **Frontend Loads:** The main application user interface should appear, looking and behaving as it did when previously served by a dedicated Next.js development server.
    *   **No Console Errors:** Open your browser's developer console (usually by pressing F12 and selecting the "Console" tab). Check for any critical JavaScript errors (usually in red).
    *   **WebSocket Connection:** The application communicates with the backend via WebSockets.
        *   In the developer console's "Network" tab (filter by "WS" or "WebSockets"), you should see a successful connection to an endpoint like `ws://localhost:8000/ws`. The status code should be 101 (Switching Protocols).
        *   The application UI might also indicate a successful connection or agent readiness.
    *   **Static Assets:** Ensure that images, CSS, and JavaScript files are loading correctly.
        *   In the developer console's "Network" tab, check for any requests that return a 404 (Not Found) error, particularly for files under `/_next/static/...` or `/public/...`.
    *   **Basic Functionality (if API keys are configured):**
        *   Try sending a simple query or interacting with an agent if your environment variables for LLM API keys are set up.
        *   Check if UI elements that depend on backend data (e.g., session history, if applicable) are loading correctly.

3.  **Troubleshooting Tips:**
    *   **Page Doesn't Load / Server Error:** Check the console where you ran `python ws_server.py` for any error messages or tracebacks.
    *   **Frontend Assets Missing (404 Errors):**
        *   Verify that the `frontend_build` directory exists at the project root.
        *   Ensure all assets were copied correctly as per Section 7 (e.g., `frontend_build/.next/static`, `frontend_build/public`, `frontend_build/index.html`).
        *   Check the paths in `ws_server.py` where `StaticFiles` and `FileResponse` are configured, ensuring they match `frontend_build`.
    *   **WebSocket Connection Issues:**
        *   Confirm the backend server is running.
        *   Check for errors in the server console related to WebSocket handling.
        *   Look for errors in the browser's console related to the WebSocket connection attempt.
    *   **General Issues:** The browser's developer console (both "Console" and "Network" tabs) is your primary tool for diagnosing frontend-related problems.

By performing these checks, you can be more confident that the unified local build and run setup is functioning as expected.

## 10. Optional Cleanup Steps After Local Testing

After you have finished local testing, you may want to clean up your environment. These steps are optional.

1.  **Stop the Python Server:**
    If the server is still running in your terminal, press `Ctrl+C` to stop it.

2.  **Deactivate Python Virtual Environment:**
    If your virtual environment is active, you can deactivate it:
    ```bash
    deactivate
    ```
    This command should work in most shells (Linux, macOS, Windows Git Bash, WSL).

3.  **Remove Created Directories and Files (Optional):**
    These commands will permanently delete files and directories. Use with caution.
    *   **`frontend_build` directory (contains prepared frontend assets):**
        *   Unix-like (Linux/macOS): `rm -rf frontend_build`
        *   Windows (Command Prompt/PowerShell): `rd /s /q frontend_build`
    *   **`workspace_local` directory (if created as per Section 8 example):**
        *   Unix-like (Linux/macOS): `rm -rf workspace_local`
        *   Windows (Command Prompt/PowerShell): `rd /s /q workspace_local`
    *   **Frontend `node_modules` (to save disk space):**
        *   Navigate to `frontend` directory: `cd frontend`
        *   Unix-like (Linux/macOS): `rm -rf node_modules`
        *   Windows (Command Prompt/PowerShell): `rd /s /q node_modules`
        *   Navigate back: `cd ..`
    *   **Python virtual environment `.venv` (to reclaim all space used by it):**
        *   Unix-like (Linux/macOS): `rm -rf .venv`
        *   Windows (Command Prompt/PowerShell): `rd /s /q .venv`

4.  **Unset Environment Variables:**
    *   If you set environment variables using `export VAR=value` (Linux/macOS) or `$env:VAR="value"` (PowerShell) in your terminal, they will typically only last for that shell session. Closing the terminal or starting a new session will clear them.
    *   If you modified shell profile scripts (e.g., `.bashrc`, `.zshrc`, PowerShell Profile), you would need to manually edit those files to remove the variables.
    *   If you created a `.env` file for the project, you can simply delete it or keep it for future use.

These cleanup steps help maintain a tidy project directory and system environment.The `LOCAL_BUILD_PREREQUISITES.md` file has been successfully updated with the new section "10. Optional Cleanup Steps After Local Testing".

The new section includes:
-   Stopping the Python server (`Ctrl+C`).
-   Deactivating the Python virtual environment (`deactivate`).
-   Optional commands for removing created directories:
    -   `frontend_build`
    -   `workspace_local` (example)
    -   `frontend/node_modules`
    -   `.venv`
    -   Provides both Unix-like (`rm -rf`) and Windows (`rd /s /q`) commands.
-   Guidance on unsetting environment variables, distinguishing between session-only variables and those in shell profiles or `.env` files.

The "Summary of Setup Steps (Conceptual)" was removed, as the document now flows from prerequisites through setup, running, verification, and finally cleanup, providing a complete lifecycle for local testing.

The documentation for local build and run, including cleanup, is now complete.

The subtask is complete. I will submit the report.
