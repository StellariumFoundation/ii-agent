# II-Agent Desktop

II-Agent Desktop is a cross-platform desktop application providing a client interface for interacting with the II-Agent backend. It allows users to send instructions to the agent, view results, and manage files within the agent's workspace, all from a native desktop environment.

This application is built using Neutralinojs, leveraging web technologies (HTML, CSS, JavaScript) for the user interface while providing access to native desktop capabilities.

## Prerequisites

*   **II-Agent Backend:** The II-Agent Python backend server (`ws_server.py`) must be running and accessible network-wise from the machine where II-Agent Desktop is used. By default, the desktop application will attempt to connect to `ws://localhost:8000/ws`.
*   **Neutralinojs Environment (for building from source):**
    *   Node.js and npm.
    *   Neutralinojs CLI: `npm install -g @neutralinojs/neu`

## Building from Source (Conceptual)

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>/ii_agent_desktop
    ```
2.  **Install Dependencies (if any specific to the Neutralino app itself - typically not needed for basic HTML/JS/CSS):**
    If there were frontend build steps (e.g., for TypeScript, SASS), they would go here. For this project, assets are directly used.
3.  **Build the Application:**
    The Neutralinojs CLI packages the application.
    ```bash
    neu build --release
    ```
    This command will create distributables (executables and resource files) in a `dist` subdirectory within `ii_agent_desktop`.

## Running the Application (Conceptual)

After building, executables will be available in `ii_agent_desktop/dist/ii-agent-desktop/`.

*   **Windows:** Run `ii-agent-desktop-win_x64.exe` (or similar).
*   **macOS:** Run `ii-agent-desktop-mac_x64` (or similar, might need to be made executable: `chmod +x ii-agent-desktop-mac_x64`). You might also need to allow running apps from unidentified developers in System Settings.
*   **Linux:** Run `ii-agent-desktop-linux_x64` (or similar, might need to be made executable: `chmod +x ii-agent-desktop-linux_x64`).

Alternatively, during development, you can run the application using:
```bash
neu run
```
This will launch the application directly without packaging it.

## Basic Usage

1.  **Launch the Application:** Start II-Agent Desktop as described above.
2.  **Backend Connection:**
    *   The application will automatically attempt to connect to the default II-Agent backend URL (`ws://localhost:8000/ws`).
    *   The status bar at the top will indicate "Connecting to backend...", then "Connected. Initializing agent...", and finally "Agent initialized and ready." along with a Session ID.
    *   If connection fails, an error message will be displayed. Ensure your II-Agent backend is running.
3.  **Sending Instructions:**
    *   Type your instructions or questions for the agent into the text area at the bottom.
    *   Click the "Send" button or press Enter (without Shift) to submit.
4.  **Viewing Interaction:**
    *   Your messages, agent responses, tool calls, and tool results will appear in the main chat area.
    *   Different message types are styled distinctly for clarity.
5.  **Uploading Files:**
    *   Click the "Upload File" button.
    *   A native file dialog will appear, allowing you to select a file from your computer.
    *   Upon selection, the file will be uploaded to the agent's current workspace.
    *   A system message will confirm the upload and provide the path of the file within the agent's workspace.
    *   You can then instruct the agent to use the uploaded file, e.g., "Analyze the uploaded file: /uploads/filename.txt".
6.  **Desktop Interactions (via Agent):**
    *   If the agent uses the `desktop_interaction` tool (NeutralinoBridgeTool), you might see native desktop notifications or file dialogs initiated by the agent. Respond to these dialogs as you normally would.

## Debugging

*   Raw JSON events exchanged with the server are displayed in the "Raw Server Events (for debugging)" section at the bottom of the application window. This can be useful for developers or for troubleshooting.
*   Right-click and select "Inspect Element" (if `enableInspector` is true in `neutralino.config.json`) to open developer tools for the web view.

---
This README provides a basic overview. For more detailed information on II-Agent backend capabilities, refer to the main project documentation.
