# Local Build and Run Prerequisites

This document outlines the necessary software, tools, and configurations required to build and run this project locally using the provided helper scripts.

## 1. Operating System

*   A Unix-like environment (Linux or macOS) is recommended, as scripts use Bash and common Unix commands.
*   Windows users: You may need to use Windows Subsystem for Linux (WSL) or Git Bash (ensure Bash shell compatibility for scripts). Command Prompt/PowerShell native equivalents for script content would be needed if not using a Bash environment.

## 2. Software Versions

*   **Python:**
    *   Version: Python 3.10 or higher (as per `pyproject.toml`). `.python-version` specifies `3.10`.
*   **Node.js:**
    *   Version: Node.js v18.x.
*   **Yarn (Package Manager for Node.js):**
    *   Yarn Classic (v1.x).

## 3. Build and Installation Tools

*   **For Python:**
    *   `pip` or `uv` (recommended).
*   **For Node.js (Frontend):**
    *   `yarn`.
*   **General:**
    *   Bash shell (for running `.sh` scripts).

## 4. Environment Variables

(This section remains largely the same, but the WORKSPACE_PATH explanation is slightly adjusted for consistency with `setup-backend.sh`)

Several environment variables are critical. Create a `.env` file in the project root (from `.env.example`) or set them in your shell.

Key variables include:

*   **API Keys (from `.env.example`):**
    *   `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, etc.
*   **Google Cloud (if using Vertex AI services):**
    *   `GOOGLE_APPLICATION_CREDENTIALS`, `PROJECT_ID`, `REGION`.
*   **Workspace Configuration:**
    *   `WORKSPACE_PATH`: Defines the directory for agent workspaces. If not set, `scripts/setup-backend.sh` and the server run step will default to `./workspace_local`. It's recommended to set this explicitly (e.g., `export WORKSPACE_PATH=${PWD}/workspace_local`) or ensure the default is suitable.
*   **Frontend (from `.env.example`):**
    *   `STATIC_FILE_BASE_URL`: Usually `http://localhost:PORT/` for local setup.

**Note:** Ensure `GOOGLE_APPLICATION_CREDENTIALS` file is accessible and `WORKSPACE_PATH` (or its default `./workspace_local`) exists (the `setup-backend.sh` script helps with this).

## 5. Installing Python Dependencies Locally

(This section remains the same)

Follow these steps to set up a Python virtual environment and install the necessary backend dependencies. These commands should be run from the project root directory (where `pyproject.toml` is located).

1.  **Create a Python Virtual Environment:**
    ```bash
    python3 -m venv .venv
    ```
2.  **Activate the Virtual Environment:**
    *   Linux/macOS: `source .venv/bin/activate`
    *   Windows (Git Bash/WSL): `source .venv/Scripts/activate`
    *   (See full file for other Windows shells)
3.  **Install Dependencies:**
    *   Using `uv` (Recommended): `uv pip install -e .`
    *   Using `pip`: `pip install -e .`
4.  **Verification (Optional):**
    ```bash
    python -c "import fastapi; print(f'FastAPI version: {fastapi.__version__}')"
    ```

## 6. Building Frontend Assets Locally (Script-based)

This step uses a script to install frontend dependencies and build the static assets. Run this from the project root directory.

```bash
bash scripts/build-frontend.sh
```
This script will:
1.  Navigate into the `frontend` directory.
2.  Run `yarn install --frozen-lockfile` to install dependencies.
3.  Run `yarn build` to compile the Next.js application.
4.  Navigate back to the project root.
The built assets are located in `frontend/.next/`.

## 7. Preparing Built Frontend Assets for the Python Server (Script-based)

This step uses a script to copy the built frontend assets from `frontend/.next/` and `frontend/public/` into the `frontend_build/` directory, which the Python server uses. Run this from the project root directory.

```bash
bash scripts/prepare-frontend-assets.sh
```
This script will:
1.  Ensure it's run from the project root.
2.  Clean and create the `frontend_build/` directory.
3.  Copy necessary assets (`.next/static`, `public/*`, `index.html`) into `frontend_build/`.

**Note for Windows Users:** The scripts `build-frontend.sh` and `prepare-frontend-assets.sh` use Bash and Unix commands (`cd`, `cp -R`, `rm -rf`). Ensure you run them in a Bash-compatible environment like Git Bash or WSL.

## 8. Running the Python Backend Server Locally

Once dependencies are installed, frontend assets built and prepared, and environment variables configured, you can run the Python backend server.

1.  **Ensure You Are in the Project Root Directory.**

2.  **Activate the Python Virtual Environment:**
    (If not already active)
    *   Linux/macOS: `source .venv/bin/activate`
    *   Windows: (See Section 5 for specific commands)

3.  **Run Backend Setup Script:**
    This script ensures the workspace directory (defined by `WORKSPACE_PATH` or defaulting to `./workspace_local`) is created.
    ```bash
    bash scripts/setup-backend.sh
    ```

4.  **Set/Confirm Environment Variables:**
    (As detailed in Section 4). If using the default workspace, ensure `WORKSPACE_PATH` is either unset (to use the default `./workspace_local` from `setup-backend.sh` and the server) or set to `./workspace_local`.
    Example if setting manually for the session:
    ```bash
    export WORKSPACE_PATH=./workspace_local
    # Note: scripts/setup-backend.sh already created this if WORKSPACE_PATH was not set otherwise.
    ```

5.  **Run the FastAPI Server:**
    ```bash
    python ws_server.py --port 8000
    ```
    (Or `uvicorn ws_server:app --host 0.0.0.0 --port 8000 --reload` for development).

6.  **Server Output:**
    Expect output like `Uvicorn running on http://0.0.0.0:8000`.

## 9. Verifying the Application Locally

(This section remains the same - details accessing http://localhost:8000, checking UI, console, WebSockets, static assets, and basic functionality, plus troubleshooting tips.)

## 10. Overall Local Build and Run Workflow

This summarizes the sequence of commands from the project root for a full local setup and run:

1.  **Initial Setup (Per Environment):**
    *   Install Python 3.10+, Node.js v18.x, Yarn.
    *   Clone repository.
    *   `python3 -m venv .venv` (Create Python virtual environment)

2.  **Activate Python Environment (New Terminal Session):**
    *   `source .venv/bin/activate` (or Windows equivalent)

3.  **Install Python Dependencies:**
    *   `uv pip install -e .` (or `pip install -e .`)

4.  **Build Frontend:**
    *   `bash scripts/build-frontend.sh`

5.  **Prepare Frontend Assets for Server:**
    *   `bash scripts/prepare-frontend-assets.sh`

6.  **Setup Backend (e.g., ensure workspace):**
    *   `bash scripts/setup-backend.sh`

7.  **Set Environment Variables:**
    *   Create/update `.env` file, or `export VAR=value` for current session. (Ensure `WORKSPACE_PATH` aligns with `setup-backend.sh` if set manually).

8.  **Run Server:**
    *   `python ws_server.py --port 8000`

9.  **Verify in Browser:**
    *   Open `http://localhost:8000`. Check UI, console, WebSockets. (Details in Section 9).

10. **Cleanup (Optional, after testing):**
    *   `Ctrl+C` in server terminal.
    *   `deactivate`.
    *   (See Section 11 for `rm -rf` commands for `frontend_build`, `workspace_local`, etc.)

## 11. Optional Cleanup Steps After Local Testing
(This section was previously Section 10, now renumbered. Content remains the same.)

After you have finished local testing, you may want to clean up your environment... (details on stopping server, deactivating venv, removing directories, unsetting env vars).The `LOCAL_BUILD_PREREQUISITES.md` file has been updated.

Key changes:
1.  **Section 6 ("Building Frontend Assets Locally")** now instructs users to run `bash scripts/build-frontend.sh`.
2.  **Section 7 ("Preparing Built Frontend Assets for the Python Server")** now instructs users to run `bash scripts/prepare-frontend-assets.sh`. It also includes a note for Windows users to run these scripts in a Bash-compatible environment.
3.  **Section 8 ("Running the Python Backend Server Locally")** now includes a new step to run `bash scripts/setup-backend.sh` to ensure the workspace directory is created. The environment variable `WORKSPACE_PATH` explanation in Section 4 and Section 8 was also slightly refined for consistency with this script.
4.  **Section 10 (previously "Summary of Setup Steps (Conceptual)")** has been renamed to **"Overall Local Build and Run Workflow"**. It now provides a more explicit, numbered list of steps from initial setup to verification, incorporating the new script-based commands.
5.  **Section 11 ("Optional Cleanup Steps After Local Testing")** is the renumbered version of the previous cleanup section, with its content unchanged but correctly placed after the new overall workflow.

The document now reflects the script-based local build process.

The subtask is complete. I will submit the report.
