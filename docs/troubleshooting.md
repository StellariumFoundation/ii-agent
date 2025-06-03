# Troubleshooting Guide

This guide provides solutions and tips for common issues you might encounter while setting up or running the II-Agent.

## General Issues

*   **Issue:** Python dependency conflicts or errors during `uv pip install` or `pip install -e .`.
    *   **Solution:**
        *   Ensure you are using the recommended Python version (Python 3.10+, see `pyproject.toml` for exact details).
        *   Always use a virtual environment (`python -m venv .venv && source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\activate` on Windows) to isolate dependencies.
        *   If you encounter issues with `uv`, ensure it's correctly installed and up-to-date. You can also try falling back to `pip install -r requirements.txt` if a `requirements.txt` file is generated/available, though `uv` or `pip install -e .` with `pyproject.toml` is preferred.
        *   For persistent issues, try deleting your virtual environment and recreating it.

## Docker Issues

*   **Issue:** Docker container fails to start, or you see errors like "container name is already in use."
    *   **Solution:**
        *   Run `docker-compose down` (or `./stop.sh`) to stop and remove existing containers associated with the project.
        *   Then, try `docker-compose up --build` (or `./start.sh --build`).
        *   If problems persist, use `docker-compose up --build --force-recreate` (or `./start.sh --build --force-recreate`) to ensure containers are completely rebuilt from scratch.

*   **Issue:** Changes to backend code are not reflected in the Docker container.
    *   **Solution:**
        *   Ensure you are rebuilding the image: `docker-compose up --build` (or `./start.sh --build`).
        *   The Docker setup for the backend typically mounts the `src` directory into the container, so Python code changes should reflect automatically. If they don't, a full rebuild (`--force-recreate`) might resolve caching or volume issues.

## API Key and Configuration Issues

*   **Issue:** Agent reports errors related to API keys (e.g., "Invalid API Key," "AuthenticationError").
    *   **Solution:**
        *   Double-check that the correct API keys (e.g., `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, etc.) are correctly set in your root `.env` file. This file is used by Docker Compose to inject variables into the backend container.
        *   If running `cli.py` or `ws_server.py` directly (not in Docker), ensure these variables are exported in your shell environment.
        *   Ensure there are no typos, extra spaces, or quotation marks around the actual key values in the `.env` file.
        *   Verify that the API keys are active and have the necessary permissions/credits with the respective service providers.

*   **Issue:** A specific tool requiring an API key is not working (e.g., `WebSearchTool`, `ImageSearchTool`).
    *   **Solution:**
        *   Confirm the relevant API key (e.g., `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `JINA_API_KEY`) is correctly set in your environment / `.env` file.
        *   Some tools might depend on specific `tool_args` for activation beyond just API keys; refer to `docs/tools_reference.md`.

## Local LLM Setup (e.g., LMStudio, Ollama via OpenAI-compatible endpoint)

*   **Issue:** Cannot connect to local LLM (e.g., using LMStudio).
    *   **Solution:**
        *   Ensure your local LLM server (LMStudio, Ollama with OpenAI compatibility enabled) is running.
        *   Verify the `OPENAI_BASE_URL` in your `.env` file (or environment) is correct (e.g., `http://<your-lmstudio-host-ip>:1234/v1` for LMStudio). Remember to use your actual local network IP if running the agent in a different environment (like WSL or Docker) than your LLM server host.
        *   Confirm the model is loaded in your local LLM server and is compatible with OpenAI API conventions (especially for function calling/tool use if expected).
        *   Check your local LLM server logs for any specific error messages or incoming request details.
        *   Ensure no firewall on your host machine or within your network is blocking the connection to the local LLM server's port from where the agent is running.
        *   The `OPENAI_API_KEY` can usually be set to a dummy value (e.g., "lmstudio") when using LMStudio if no API key is configured on the server side.

## Agent Behavior Issues

*   **Issue:** Agent is not using a specific tool I expect it to use.
    *   **Solution:**
        *   Verify the tool is intended to be active. Some tools are enabled by default, others require specific `tool_args` during agent initialization (via CLI or WebSocket `init_agent` message). Consult `docs/tools_reference.md`.
        *   The LLM decides which tool to use based on your prompt and the descriptions of available tools. Ensure your prompt is clear, provides sufficient context, and implicitly or explicitly suggests the need for the tool's capability.
        *   Check if the tool has dependencies (like API keys) that might not be met.

*   **Issue:** Agent's responses are not as expected, it seems to be stuck, or provides very short/unhelpful answers.
    *   **Solution:**
        *   **Try a different LLM model:** If you have multiple models configured (e.g., via `--model-name` in CLI or `model_name` in `init_agent` WebSocket message), experiment with another one.
        *   **Adjust the system prompt:** While the default system prompts are optimized, for specific tasks, you might experiment by creating a custom prompt.
        *   **Refine your user prompt:** Make your request more specific, provide more context, or break down a complex task into smaller steps.
        *   **Check agent logs:** The console output (especially if not minimized) or the `agent_logs.txt` file can provide insights into the agent's internal state, tool calls, and any errors encountered.
        *   **Context Manager:** Experiment with the `--context-manager` option (e.g., `llm-summarizing` vs. `amortized-forgetting`) if you suspect issues with how conversation history is being handled on very long interactions.
        *   **Token Limits:** The agent might be hitting `max_output_tokens_per_turn` or overall context window limits. While memory management strategies try to mitigate this, very complex turns might still be affected.

## Frontend Issues

*   **Issue:** Frontend UI is not loading or not connecting to the backend.
    *   **Solution:**
        *   Ensure the backend WebSocket server (`ws_server.py`) is running.
        *   Verify the `NEXT_PUBLIC_API_URL` in `frontend/.env.local` (or your frontend environment) correctly points to the backend WebSocket server (e.g., `http://localhost:8000`).
        *   Check your browser's developer console (Network and Console tabs) for any errors related to WebSocket connection or JavaScript issues.

*   **Issue:** Code editor component is not showing up or not working in the frontend.
    *   **Solution:**
        *   Ensure the `NEXT_PUBLIC_VSCODE_URL` environment variable is correctly set in the `frontend/.env.local` file (or your frontend environment).
        *   This URL must point to a running instance of a VS Code web server (like `code-server`) that is accessible from your browser. If this variable is not set or the URL is unreachable, the embedded editor will not function.

---
If your issue is not listed here, or the solutions do not work:
1.  **Check Logs:** Examine `agent_logs.txt` (or the path specified by `--logs-path`) and any relevant server or Docker logs for detailed error messages.
2.  **GitHub Issues:** Review the project's GitHub issues page to see if others have reported similar problems.
3.  **Open a New Issue:** If you suspect a bug or an unaddressed problem, consider opening a new issue on GitHub. Please provide detailed information, including:
    *   Steps to reproduce the issue.
    *   Relevant configuration details (OS, Python version, Docker version, agent settings).
    *   Error messages and log snippets.
    *   Your expected outcome.
```
