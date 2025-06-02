// communication.js for self-contained Python backend

let mainWebSocket = null; // WebSocket connection to the local Python server
let pythonProcess = null; // Info about the spawned Python process
let pythonServerPort = null; // Port the Python server is running on

// Device ID functions (can be kept as they are)
function generateDeviceId() {
  return 'desktop_device_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15);
}

async function getOrStoreDeviceId() {
  const key = 'iiAgentDesktopDeviceId';
  try {
    let storedData = await Neutralino.storage.getData(key);
    if (storedData && typeof storedData === 'string' && storedData.startsWith('desktop_device_')) {
        return storedData;
    } else if (storedData && storedData.id) { 
        return storedData.id;
    }
  } catch (err) {
    // Normal on first run or if storage is cleared
  }
  const newId = generateDeviceId();
  try {
    await Neutralino.storage.setData(key, newId);
  } catch (err) {
    console.error("Error saving new device ID to Neutralino storage:", err);
  }
  return newId;
}

// Main function to initialize communication with the embedded Python backend
async function initCommunication() { 
  const deviceId = await getOrStoreDeviceId(); // Needed for WebSocket query param
  updateStatus("Starting embedded Python backend...", false); // updateStatus is in main.js

  try {
    const appDataPath = await Neutralino.filesystem.getPath('data');
    // Define a root directory within Neutralino's data path for all app's backend data (workspaces, logs)
    const backendDataRootPath = `${appDataPath}/ii_agent_backend_data`; 
    await Neutralino.filesystem.createDirectory(backendDataRootPath); // Ensure it exists

    // Command to execute: path to executable + workspace_path argument
    // The executable is expected to be in app/bin/ii_agent_core_service/ relative to resourcesPath (which is app/)
    const executableName = 'ii_agent_core_service'; // Must match PyInstaller output app_name
    const commandBase = NL_OS === 'Windows' ? 
        `./bin/${executableName}/${executableName}.exe` : 
        `./bin/${executableName}/${executableName}`;
    
    const command = `${commandBase} "${backendDataRootPath}"`;
    
    console.log(`Spawning Python backend with command: ${command}`);
    // Using appendMessage from main.js to log to UI
    appendMessage('system-message', `Spawning Python backend...`);
    appendMessage('system-message', `Cmd: ${commandBase} "{appData}/ii_agent_backend_data"`);


    // Clear any old listeners before spawning a new process to prevent multiple handlers
    Neutralino.events.off("extensionStdOut", handlePythonStdOutForPort);
    Neutralino.events.off("extensionStdErr", handlePythonStdErr);
    Neutralino.events.off("spawnedProcess", handlePythonExit);

    pythonProcess = await Neutralino.extensions.spawnProcess(command);
    appendMessage('system-message', `Python backend process launched. PID: ${pythonProcess.id}. Waiting for port...`);

    Neutralino.events.on("extensionStdOut", handlePythonStdOutForPort);
    Neutralino.events.on("extensionStdErr", handlePythonStdErr);
    Neutralino.events.on("spawnedProcess", handlePythonExit);

  } catch (err) {
    console.error("Error launching Python backend:", err);
    appendMessage('error-message', `Error launching Python backend: ${err.message || JSON.stringify(err)}`);
    updateStatus(`Python backend launch error: ${err.message || 'Unknown'}`, true);
    pythonProcess = null;
  }
}

function handlePythonStdOutForPort(evt) {
    if (!pythonProcess || evt.detail.id !== pythonProcess.id || pythonServerPort) return; 
    const data = evt.detail.data;
    // Log all stdout from Python process until port is found, for debugging
    appendMessage('system-message', `[PY STDOUT]: ${data.trim()}`); 

    if (data.startsWith("PORT:")) {
        pythonServerPort = parseInt(data.substring(5).trim(), 10);
        if (pythonServerPort) {
            appendMessage('system-message', `Python backend reported port: ${pythonServerPort}. Connecting WebSocket...`);
            updateStatus(`Python backend ready on port ${pythonServerPort}. Connecting...`, false);
            connectToLocalPythonWs(pythonServerPort);
            // Optional: Once port is captured, you might consider removing this stdout listener if it's noisy,
            // or keep it for further Python logs if Python is configured to use stdout for general logging.
            // However, Python script uses stderr for its own logging.
        } else {
            appendMessage('error-message', `Python backend reported invalid port: ${data}`);
            updateStatus('Python backend port error.', true);
        }
    }
}

function handlePythonStdErr(evt) {
    if (pythonProcess && evt.detail.id === pythonProcess.id) {
        // These are logs from the Python script's stderr
        appendMessage('system-message', `[PY STDERR]: ${evt.detail.data.trim()}`);
        // Don't necessarily set main status to error for all stderr, could be debug info
        // updateStatus(`Python backend: ${evt.detail.data.trim()}`, false); 
    }
}

function handlePythonExit(evt) {
    if (pythonProcess && evt.detail.id === pythonProcess.id && evt.detail.action === 'exit') {
        appendMessage('error-message', `Python backend (PID ${pythonProcess.id}) exited with code: ${evt.detail.data}.`);
        updateStatus("Python backend exited.", true);
        if (mainWebSocket) mainWebSocket.close(); // Close WebSocket connection if it exists
        
        // Clean up event listeners for the exited process
        Neutralino.events.off("extensionStdOut", handlePythonStdOutForPort);
        Neutralino.events.off("extensionStdErr", handlePythonStdErr);
        Neutralino.events.off("spawnedProcess", handlePythonExit);

        mainWebSocket = null;
        pythonProcess = null;
        pythonServerPort = null; // Reset port so it can be rediscovered if relaunched
    }
}

async function connectToLocalPythonWs(port) {
    if (mainWebSocket && (mainWebSocket.readyState === WebSocket.OPEN || mainWebSocket.readyState === WebSocket.CONNECTING)) {
        appendMessage('system-message', "WebSocket connection attempt already in progress or open.");
        return;
    }

    const deviceId = await getOrStoreDeviceId(); 
    const wsUrl = `ws://localhost:${port}?device_id=${deviceId}`; 
    appendMessage('system-message', `Connecting to main WebSocket: ${wsUrl}`);
    mainWebSocket = new WebSocket(wsUrl);

    mainWebSocket.onopen = () => {
        updateStatus('Connected to II-Agent backend. Initializing agent...', false);
        sendMessageToServer({ 
            type: "init_agent", // Corresponds to EventType.INIT_AGENT in Python
            content: {
                model_name: "claude-3-haiku-20240307", // Example model
                tool_args: { 
                    sequential_thinking: true, 
                    browser: false, // Browser tool likely won't work easily with embedded Python
                    neutralino_bridge: true // Enable the bridge tool
                }
                // Pass workspace_path if needed by init_agent on backend,
                // but backend now gets it via CLI arg.
            }
        });
    };

    mainWebSocket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        logRawEvent(message); // From main.js for raw debugging

        // Store session_uuid if received from CONNECTION_ESTABLISHED
        if (message.type === "connection_established" && message.content && message.content.session_uuid) {
            currentSessionUUID = message.content.session_uuid; // Set global in main.js
            console.log("Session UUID from LOCAL backend:", currentSessionUUID);
            // The rest of the event display is handled by handleRealtimeEvent
        }
        handleRealtimeEvent(message); // From main.js to render in UI
    };

    mainWebSocket.onerror = (errorEvent) => {
        // The errorEvent object itself is often not very informative for WebSockets.
        // More detailed errors are usually logged to the browser console.
        let errorMessage = 'WebSocket connection error. See browser console for details.';
        if (errorEvent.message) errorMessage = errorEvent.message; // Some environments might provide a message
        
        appendMessage('error-message', `Main WebSocket Error: ${errorMessage}`);
        updateStatus(`Main WebSocket Error: ${errorMessage}`, true);
        console.error("Main WebSocket Error:", errorEvent);
    };

    mainWebSocket.onclose = (event) => {
        appendMessage('system-message', `Disconnected from II-Agent backend. Code: ${event.code}, Reason: ${event.reason || 'N/A'}`);
        updateStatus("Disconnected from II-Agent backend.", true);
        mainWebSocket = null; 
        // pythonServerPort = null; // Keep port if process might still be running, or nullify if process also exited.
                                 // handlePythonExit handles nullifying pythonServerPort.
    };
}

// This function is intended to be called by main.js
function sendMessageToServer(messageObject) { 
    if (mainWebSocket && mainWebSocket.readyState === WebSocket.OPEN) {
        mainWebSocket.send(JSON.stringify(messageObject));
        logRawEvent({ SENT_TO_LOCAL_PY: messageObject }); // logRawEvent is in main.js
    } else {
        updateStatus('Not connected to II-Agent backend. Cannot send message.', true);
        console.error('Main WebSocket not open. Cannot send message.');
    }
}

// Function to terminate Python process on app exit, called from main.js
async function cleanupPythonProcess() {
    appendMessage('system-message', `Cleaning up Python process...`);
    if (mainWebSocket && mainWebSocket.readyState === WebSocket.OPEN) {
        mainWebSocket.close(); // Gracefully close WebSocket first
    }
    if (pythonProcess && pythonProcess.id) {
        try {
            appendMessage('system-message', `Terminating Python backend (PID: ${pythonProcess.id})...`);
            await Neutralino.extensions.killProcess(pythonProcess.id);
            // appendMessage('system-message', 'Python backend process kill signal sent.'); 
            // handlePythonExit will confirm actual exit.
        } catch (err) {
            appendMessage('error-message', `Error terminating Python backend: ${err.message || JSON.stringify(err)}`);
            console.error("Error killing Python process:", err);
        }
    }
    pythonProcess = null; // Clear process info
}

// Expose functions to be callable from main.js via a global object
// This is a simple way to manage scope between main.js and communication.js
window.IIA_Desktop_EmbeddedComms = {
    initCommunication: initCommunication,
    sendMessageToServer: sendMessageToServer,
    cleanupPythonProcess: cleanupPythonProcess
    // getOrStoreDeviceId is not directly called by main.js after this refactor
};

console.log("communication.js loaded for self-contained Python backend.");
