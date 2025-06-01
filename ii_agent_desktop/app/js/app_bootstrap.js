// ii_agent_desktop/app/js/app_bootstrap.js

// --- Global Promises for Neutralino Ready and Python Backend Ready ---
// These allow the React app to wait for these initializations.
if (!window.NL_READY) {
    window.NL_READY = new Promise(resolve => Neutralino.events.on("ready", resolve));
}
if (!window.PYTHON_BACKEND_READY) {
    window.PYTHON_BACKEND_READY = new Promise(resolve => {
        window.resolvePythonBackendReady = resolve;
    });
}

// --- Python Process Management and Port/Path Injection (IIFE) ---
(async () => {
    try {
        await window.NL_READY; // Wait for Neutralino to be ready
    } catch (e) {
        console.error("Bootstrap: Neutralino ready event error or not firing:", e);
        // If Neutralino itself isn't ready, we can't proceed with its APIs.
        // This case should ideally not happen if this script is loaded correctly by Neutralino.
        if (window.resolvePythonBackendReady) { // Signal failure if promise was set up
            window.resolvePythonBackendReady({ success: false, error: "Neutralino failed to initialize." });
        }
        return; // Stop execution of this bootstrap script
    }


    // Declare globals for React app to pick up
    window.NL_EMBEDDED_PYTHON_PORT = null;
    window.NL_APP_DATA_PATH = null;
    window.NL_PYTHON_WORKSPACE_ROOT = null;
    window.NL_DEVICE_ID = null; // For React app to use in WebSocket connection

    let pythonProcess = null;

    // Simple status update for pre-React UI (if any)
    function bootstrapUpdateStatus(message, isError = false) {
        const statusEl = document.getElementById('bootstrap-status');
        if (statusEl) {
            const p = document.createElement('p');
            p.style.color = isError ? 'red' : 'inherit';
            p.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
            statusEl.appendChild(p);
            statusEl.scrollTop = statusEl.scrollHeight;
        }
        if (isError) console.error(`Bootstrap Status: ${message}`);
        else console.log(`Bootstrap Status: ${message}`);
    }

    bootstrapUpdateStatus("app_bootstrap.js: Initializing...");

    async function getOrStoreDeviceId_Bootstrap() {
        const key = 'iiAgentDesktopDeviceId_v2'; // Use a distinct key
        try {
            // Neutralino.storage.getData might return null or throw if key not found
            const storedData = await Neutralino.storage.getData(key);
            if (storedData && typeof storedData === 'object' && storedData.id) return storedData.id;
            if (typeof storedData === 'string') return storedData; // Older format if any
        } catch (err) { console.warn("Bootstrap: No stored device ID or error accessing storage (normal on first run)."); }

        const newId = 'device_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
        try {
            await Neutralino.storage.setData(key, { id: newId });
            bootstrapUpdateStatus(`Generated and stored new device ID: ${newId}`);
        }
        catch (err) { console.error("Bootstrap: Error saving new device ID:", err); }
        return newId;
    }

    window.NL_DEVICE_ID = await getOrStoreDeviceId_Bootstrap();
    bootstrapUpdateStatus(`Device ID for WebSocket: ${window.NL_DEVICE_ID}`);

    bootstrapUpdateStatus("Starting embedded Python backend...");

    try {
        window.NL_APP_DATA_PATH = await Neutralino.filesystem.getPath('data');
        window.NL_PYTHON_WORKSPACE_ROOT = `${window.NL_APP_DATA_PATH}/ii_agent_workspace_data`;
        await Neutralino.filesystem.createDirectory(window.NL_PYTHON_WORKSPACE_ROOT); // Ensure base workspace dir exists

        const executableName = 'ii_agent_core_service'; // Matches PyInstaller spec output name
        const command = (NL_OS === 'Windows' ?
            `./bin/${executableName}/${executableName}.exe` :
            `./bin/${executableName}/${executableName}`) +
            ` "${window.NL_PYTHON_WORKSPACE_ROOT}"`; // Pass workspace root as CLI argument

        bootstrapUpdateStatus(`Spawning Python: ${command.replace(window.NL_PYTHON_WORKSPACE_ROOT, "{workspace_root}")}`);

        // Clear any stale listeners from previous launches in same session (if page reloaded)
        Neutralino.events.off("extensionStdOut", handlePythonStdOutForBootstrap);
        Neutralino.events.off("extensionStdErr", handlePythonStdErrForBootstrap);
        Neutralino.events.off("spawnedProcess", handlePythonExitForBootstrap);

        pythonProcess = await Neutralino.extensions.spawnProcess(command);
        bootstrapUpdateStatus(`Python backend process launched. PID: ${pythonProcess.id}. Waiting for port...`);

        Neutralino.events.on("extensionStdOut", handlePythonStdOutForBootstrap);
        Neutralino.events.on("extensionStdErr", handlePythonStdErrForBootstrap);
        Neutralino.events.on("spawnedProcess", handlePythonExitForBootstrap);

    } catch (err) {
        const errorMsg = `Python backend launch CRITICAL error: ${err.message || JSON.stringify(err)}`;
        bootstrapUpdateStatus(errorMsg, true);
        if (window.resolvePythonBackendReady) window.resolvePythonBackendReady({ success: false, error: err, deviceId: window.NL_DEVICE_ID });
        else console.error("resolvePythonBackendReady was not defined when launch error occurred.");
    }

    function handlePythonStdOutForBootstrap(evt) {
        if (!pythonProcess || evt.detail.id !== pythonProcess.id) return; // Not our process

        const data = evt.detail.data;
        // Log all stdout for debugging until port is found
        if (!window.NL_EMBEDDED_PYTHON_PORT) { // Only log verbosely if port not yet found
             bootstrapUpdateStatus(`[PY STDOUT]: ${data.trim()}`);
        } else { // After port is found, Python stdout might be less critical or could be actual data if not careful
            console.log(`[PY STDOUT after port]: ${data.trim()}`);
        }


        if (data.startsWith("PORT:") && !window.NL_EMBEDDED_PYTHON_PORT) { // Process only if port not already set
            const portNum = parseInt(data.substring(5).trim(), 10);
            if (portNum > 0) {
                window.NL_EMBEDDED_PYTHON_PORT = portNum;
                bootstrapUpdateStatus(`Python backend reported port: ${window.NL_EMBEDDED_PYTHON_PORT}. Backend ready for React app.`, false);
                // Neutralino.events.off("extensionStdOut", handlePythonStdOutForBootstrap); // Keep listening for other stdout if needed for debug.
                if (window.resolvePythonBackendReady) window.resolvePythonBackendReady({ success: true, port: window.NL_EMBEDDED_PYTHON_PORT, deviceId: window.NL_DEVICE_ID });
                else console.error("resolvePythonBackendReady was not defined when port was received.");
            } else {
                bootstrapUpdateStatus(`Python backend reported invalid port: ${data}`, true);
                if (window.resolvePythonBackendReady) window.resolvePythonBackendReady({ success: false, error: "Invalid port from Python", deviceId: window.NL_DEVICE_ID });
            }
        }
    }

    function handlePythonStdErrForBootstrap(evt){
        if (pythonProcess && evt.detail.id === pythonProcess.id) {
             bootstrapUpdateStatus(`[PY STDERR]: ${evt.detail.data.trim()}`, true); // Assume stderr from Python is an error/warning
        }
    }

    function handlePythonExitForBootstrap(evt) {
        if (!pythonProcess || evt.detail.id !== pythonProcess.id || evt.detail.action !== 'exit') return;
        const exitCode = evt.detail.data;
        const exitMsg = `Python backend (PID ${pythonProcess.id}) exited with code: ${exitCode}. React app may not function.`;
        bootstrapUpdateStatus(exitMsg, true);

        Neutralino.events.off("extensionStdOut", handlePythonStdOutForBootstrap);
        Neutralino.events.off("extensionStdErr", handlePythonStdErrForBootstrap);
        Neutralino.events.off("spawnedProcess", handlePythonExitForBootstrap);

        pythonProcess = null;
        const previousPort = window.NL_EMBEDDED_PYTHON_PORT;
        window.NL_EMBEDDED_PYTHON_PORT = null;

        // If PYTHON_BACKEND_READY was not resolved yet (e.g. process exited before printing port)
        // or if it was resolved as success but process exited immediately.
        if (window.resolvePythonBackendReady) {
            // Check if it was already resolved to avoid errors, though a robust Promise resolves only once.
            // If it was previously resolved successfully, this signals an unexpected exit.
             window.resolvePythonBackendReady({ success: false, error: `Python process exited prematurely with code ${exitCode}. Port was ${previousPort || 'not captured'}.`, deviceId: window.NL_DEVICE_ID });
        }
    }

    // Cleanup on window close
    Neutralino.events.on("windowClose", async () => {
        bootstrapUpdateStatus("windowClose event: Cleaning up Python process...");
        if (pythonProcess && pythonProcess.id) {
            try {
                await Neutralino.extensions.killProcess(pythonProcess.id);
                bootstrapUpdateStatus(`Python backend (PID: ${pythonProcess.id}) kill signal sent.`);
            } catch (err) {
                bootstrapUpdateStatus(`Error terminating Python backend on windowClose: ${err.message || JSON.stringify(err)}`, true);
            }
        }
        // Neutralino.app.exit() will be called by the main app's windowClose handler (e.g. in React Home component or main.js)
        // This bootstrap script should not call Neutralino.app.exit() itself,
        // to allow the main application logic to also hook into windowClose if needed.
        // The main application's windowClose handler is responsible for the final app.exit().
    });

})(); // IIFE to execute the bootstrap logic
