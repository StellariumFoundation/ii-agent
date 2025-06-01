// In ii_agent_desktop/app/js/communication.js

// ... (keep existing code like backendUrl, generateDeviceId, getOrStoreDeviceId)
// Backend URL (can be made configurable later, e.g., via settings or a config file)
const backendUrl = 'ws://localhost:8000/ws';

let socket; // Keep socket global within this module

// Function to generate a simple device ID (if not using Neutralino's unique ID features extensively)
function generateDeviceId() {
  return 'desktop_device_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15);
}

// Function to get a stored device ID or generate and store a new one
// Uses Neutralino's storage API
async function getOrStoreDeviceId() {
  const key = 'iiAgentDesktopDeviceId';
  try {
    let storedData = await Neutralino.storage.getData(key);
    if (storedData && typeof storedData === 'string' && storedData.startsWith('desktop_device_')) {
        // If storedData is just a string, wrap it in an object for consistency,
        // or handle old format if you previously stored it as {id: "..."}
        return storedData;
    } else if (storedData && storedData.id) { // Compatibility with previous {id: "..."} format
        return storedData.id;
    }
    // console.log("No valid stored device ID found, generating new one.");
  } catch (err) {
    // This error often means the key doesn't exist, which is fine on first run.
    // console.log("Error retrieving device ID from storage (normal on first run):", err.message);
  }

  const newId = generateDeviceId();
  try {
    // Storing as a simple string now for simplicity with Neutralino.storage
    await Neutralino.storage.setData(key, newId);
    // console.log("New device ID generated and stored:", newId);
  } catch (err) {
    console.error("Error saving new device ID to Neutralino storage:", err);
    // Fallback to using it without storing if storage fails
  }
  return newId;
}


async function initCommunication() {
  const deviceId = await getOrStoreDeviceId();
  const fullUrl = `${backendUrl}?device_id=${deviceId}`;

  updateStatus(`Connecting to ${fullUrl}...`); // Assumes updateStatus is a global function from main.js
  socket = new WebSocket(fullUrl);

  socket.onopen = () => {
    updateStatus('Connected. Initializing agent...');
    sendMessageToServer({ // Assumes sendMessageToServer is global or part of this module
      type: "init_agent",
      content: {
        model_name: "claude-3-7-sonnet@20250219", // Default or from settings
        tool_args: {
          sequential_thinking: true, // Example, make configurable
          browser: true // Example, to see browser tool calls
        }
      }
    });
  };

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    logRawEvent(message); // Assumes logRawEvent is global defined in main.js

    // Store session_uuid if received - currentSessionUUID is global in main.js
    if (message.type === "connection_established" && message.content && message.content.session_uuid) {
        currentSessionUUID = message.content.session_uuid;
        console.log("Session UUID received:", currentSessionUUID);
        // Status update will be handled by handleRealtimeEvent in main.js
    } else if (message.type === "agent_initialized") {
        // Status update will be handled by handleRealtimeEvent in main.js
    }

    // Centralized event handling in main.js
    handleRealtimeEvent(message);
  };

  socket.onerror = (error) => {
    console.error('WebSocket Error:', error);
    updateStatus(`WebSocket Error: ${error.message || 'Could not connect.'}`, true); // updateStatus from main.js
  };

  socket.onclose = () => {
    updateStatus('Disconnected from backend.', true); // updateStatus from main.js
  };
}

function sendMessageToServer(messageObject) { // This function stays in this module
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(messageObject));
    logRawEvent({ SENT: messageObject }); // logRawEvent from main.js
  } else {
    updateStatus('Not connected to backend. Cannot send message.', true); // updateStatus from main.js
    console.error('Socket not open. Cannot send message.');
  }
}
