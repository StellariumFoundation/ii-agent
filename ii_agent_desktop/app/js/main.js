// In ii_agent_desktop/app/js/main.js

// Initialize Neutralinojs
Neutralino.init();

// Global variable for session UUID (set by communication.js via handleRealtimeEvent)
let currentSessionUUID = null;

// UI Elements (main chat) - Ensure these IDs match your index.html
const queryInput = document.getElementById('query-input');
const sendButton = document.getElementById('send-button');
const messagesDiv = document.getElementById('messages');
const rawEventsDiv = document.getElementById('raw-events'); // Debug log
const statusDiv = document.getElementById('status');
const uploadFileButton = document.getElementById('upload-file-button');

// Event Listeners for main chat
if(sendButton) {
    sendButton.addEventListener('click', sendChatMessage);
} else {
    console.error("Send button not found.");
}

if(queryInput) {
    queryInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
    });
} else {
    console.error("Query input not found.");
}

if(uploadFileButton) {
    uploadFileButton.addEventListener('click', selectAndUploadFile);
} else {
    console.error("Upload file button not found.");
}


function sendChatMessage() {
    const queryText = queryInput.value.trim();
    if (queryText) {
      if (window.IIA_Desktop_EmbeddedComms && window.IIA_Desktop_EmbeddedComms.sendMessageToServer) {
        window.IIA_Desktop_EmbeddedComms.sendMessageToServer({
            type: 'query',
            content: { text: queryText, resume: false, files: [] }
        });
        appendMessage('user-message', `You: ${queryText}`);
        queryInput.value = '';
      } else {
        updateStatus("ERROR: Communication module not ready or sendMessageToServer not found.", true);
        console.error("IIA_Desktop_EmbeddedComms.sendMessageToServer is not available.");
      }
    }
}

function logRawEvent(eventData) {
  if(!rawEventsDiv) return;
  const currentText = rawEventsDiv.textContent;
  rawEventsDiv.textContent = `${currentText}
${JSON.stringify(eventData, null, 2)}`;
  rawEventsDiv.scrollTop = rawEventsDiv.scrollHeight;
}

function appendMessage(type, textOrHtml, isHtml = false) {
  if(!messagesDiv) { console.error("Messages div not found for appendMessage"); return; }
  const messageElement = document.createElement('div');
  messageElement.classList.add('message', type);
  if (isHtml) {
    messageElement.innerHTML = textOrHtml;
  } else {
    messageElement.textContent = textOrHtml;
  }
  messagesDiv.appendChild(messageElement);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function updateStatus(message, isError = false) {
  if(!statusDiv) { console.error("Status div not found for updateStatus"); return; }
  statusDiv.textContent = message;
  statusDiv.style.backgroundColor = isError ? '#f8d7da' : '#e9ecef';
  statusDiv.style.color = isError ? '#721c24' : '#495057';
}

// Helper function to convert ArrayBuffer to Base64
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

// Modified selectAndUploadFile for WebSocket upload
async function selectAndUploadFile() {
  if (!currentSessionUUID) {
    updateStatus('Error: Session not established with local backend. Cannot upload file.', true);
    try { await Neutralino.os.showNotification('Error', 'Session not established. Please ensure backend is running.'); } catch(e){ console.error(e); }
    return;
  }

  try {
    const dialogOptions = { title: 'Select a file to upload' };
    const selectedEntries = await Neutralino.os.showOpenDialog(dialogOptions.title, dialogOptions);

    if (selectedEntries && selectedEntries.length > 0) {
      const filePath = selectedEntries[0];
      const fileName = filePath.split(/[/\\]/).pop();

      updateStatus(`Processing ${fileName} for upload...`);
      appendMessage('system-message', `Preparing to upload: ${fileName}`);

      let fileContent; // This will be ArrayBuffer for binary, string for text
      let contentToSend; // This will be base64 data URL for binary, or plain text for text

      const fileExtension = fileName.split('.').pop().toLowerCase();
      // Expanded list of common text extensions
      const textExtensions = ['txt', 'md', 'json', 'py', 'js', 'html', 'css', 'csv', 'xml', 'log', 'sh', 'java', 'c', 'cpp', 'h', 'hpp', 'rb', 'php', 'pl', 'yaml', 'ini', 'toml', 'rtf', 'tex', 'sql'];

      if (textExtensions.includes(fileExtension)) {
        try {
            fileContent = await Neutralino.filesystem.readFile(filePath); // Reads as string
            contentToSend = fileContent; // Send as plain text
            // Backend will have to handle non-base64 content if isBinary is not sent.
            // For simplicity with current Python stub, we'll send everything as base64 data URL for now.
            // So, re-encode text to base64 data URL as well.
            // This ensures backend always expects base64.
            // If sending plain text is desired, backend needs to handle it.
            const tempArrayBuffer = new TextEncoder().encode(fileContent); // string to ArrayBuffer
            contentToSend = `data:text/plain;base64,${arrayBufferToBase64(tempArrayBuffer)}`;

        } catch (e) { // Fallback to binary reading if text read fails
            console.warn(`Reading ${fileName} as text failed, trying binary: ${e.message}`);
            fileContent = await Neutralino.filesystem.readBinaryFile(filePath); // ArrayBuffer
            contentToSend = `data:application/octet-stream;base64,${arrayBufferToBase64(fileContent)}`;
        }
      } else { // For non-text extensions, read as binary directly
        fileContent = await Neutralino.filesystem.readBinaryFile(filePath); // ArrayBuffer
        contentToSend = `data:application/octet-stream;base64,${arrayBufferToBase64(fileContent)}`;
      }

      const uploadRequestMessage = {
        type: "FILE_UPLOAD_REQUEST", // Matches EventType in Python
        content: {
          fileName: fileName,
          fileContent: contentToSend, // Base64 data URL
        }
      };

      if (window.IIA_Desktop_EmbeddedComms && window.IIA_Desktop_EmbeddedComms.sendMessageToServer) {
        window.IIA_Desktop_EmbeddedComms.sendMessageToServer(uploadRequestMessage);
        updateStatus(`Upload request for ${fileName} sent. Waiting for server response...`);
        appendMessage('system-message', `Sent upload request for ${fileName}.`);
      } else {
        throw new Error("Communication module not available to send upload request.");
      }
    }
  } catch (err) {
    console.error('File Selection/Preparation Error:', err);
    updateStatus(`Error preparing file for upload: ${err.message}`, true);
    appendMessage('error-message', `Failed to prepare file for upload: ${err.message}`);
    try { await Neutralino.os.showNotification('Upload Prep Failed', `Could not prepare file: ${err.message}`); } catch(e){ console.error(e); }
  }
}


// Modified handleRealtimeEvent
function handleRealtimeEvent(eventData) {
    const type = eventData.type;
    const content = eventData.content;

    switch (type) {
        case 'user_message':
            appendMessage('user-message', `User (from server): ${content.text}`);
            break;
        case 'agent_response':
        case 'agent_response_interrupted':
            appendMessage('assistant-message', `Agent: ${content.text}`);
            break;
        case 'tool_call':
            let toolInputHtml = '<ul>';
            if(content.tool_input && typeof content.tool_input === 'object') {
                for (const key in content.tool_input) {
                toolInputHtml += `<li><strong>${key}:</strong> ${JSON.stringify(content.tool_input[key], null, 2)}</li>`;
                }
            } else { toolInputHtml += `<li>${JSON.stringify(content.tool_input, null, 2)}</li>`; }
            toolInputHtml += '</ul>';
            appendMessage('tool-call-message', `<strong>Tool Call: ${content.tool_name}</strong>${toolInputHtml}`, true);
            break;
        case 'tool_result':
            let resultText = content.result;
            try {
                if (typeof resultText === 'string') { resultText = JSON.stringify(JSON.parse(resultText), null, 2); }
                else if (typeof resultText === 'object') { resultText = JSON.stringify(resultText, null, 2); }
            } catch(e) { /* not JSON, display as is */ }
            appendMessage('tool-result-message', `<strong>Tool Result: ${content.tool_name}</strong><pre>${resultText}</pre>`, true);
            break;
        case 'system':
            appendMessage('system-message', `System: ${content.message}`);
            updateStatus(content.message);
            break;
        case 'error':
            appendMessage('error-message', `Error: ${content.message}`);
            updateStatus(`Error: ${content.message}`, true);
            break;
        case 'processing':
            updateStatus(content.message);
            break;
        case 'connection_established':
            updateStatus(`Connected. Session: ${currentSessionUUID}`); // currentSessionUUID is set in communication.js
            appendMessage('system-message', `Connection established. Workspace: ${content.workspace_path}. Session: ${currentSessionUUID}`);
            break;
        case 'agent_initialized':
            updateStatus("Agent initialized and ready.");
            appendMessage('system-message', 'Agent initialized and ready.');
            break;
        case 'NEUTRALINO_COMMAND':
            executeNeutralinoCommand(content);
            break;

        // New cases for File Upload (Task 10.1)
        case 'FILE_UPLOAD_SUCCESS': // Matches EventType in Python
            updateStatus(`File '${content.originalName}' uploaded to '${content.filePathInWorkspace}'.`, false);
            appendMessage('system-message', `Upload Success: '${content.originalName}' is available at workspace path: ${content.filePathInWorkspace}. You can now instruct the agent to use it, e.g., "Read file ${content.filePathInWorkspace}".`);
            try { Neutralino.os.showNotification('Upload Successful', `'${content.originalName}' uploaded to workspace.`); } catch(e) { console.error(e); }
            break;
        case 'FILE_UPLOAD_FAILURE': // Matches EventType in Python
            updateStatus(`File upload failed for '${content.originalName || 'unknown file'}': ${content.message}`, true);
            appendMessage('error-message', `Upload Failed for '${content.originalName || 'unknown file'}': ${content.message}`);
            try { Neutralino.os.showNotification('Upload Failed', content.message); } catch(e) { console.error(e); }
            break;

        default:
            console.warn('Received unhandled event type in main.js handleRealtimeEvent:', type, content);
            appendMessage('system-message', `Unhandled event: ${type} - ${JSON.stringify(content)}`);
    }
}

// --- NeutralinoBridgeTool Frontend Logic (Phase 4) ---
async function executeNeutralinoCommand(commandData) {
  const { command_id, action, details } = commandData;
  let status = "error"; let payload = {};
  appendMessage('system-message', `Executing desktop action via NeutralinoBridge: ${action}`);
  try {
    switch (action) {
      case 'show_notification':
        if (!details || typeof details.title !== 'string' || typeof details.content !== 'string') { throw new Error("Missing title/content for show_notification."); }
        await Neutralino.os.showNotification(details.title, details.content);
        status = "success"; payload = { message: "Notification shown." }; break;
      case 'show_save_dialog':
        if (!details || typeof details.title !== 'string') { throw new Error("Missing title for show_save_dialog."); }
        const savePath = await Neutralino.os.showSaveDialog(details.title, { defaultPath: details.defaultPath || '' });
        status = "success"; payload = { filePath: savePath }; break;
      case 'show_open_dialog':
        if (!details || typeof details.title !== 'string') { throw new Error("Missing title for show_open_dialog."); }
        const openPaths = await Neutralino.os.showOpenDialog(details.title, { defaultPath: details.defaultPath || '', multiSelections: details.multiSelections || false });
        status = "success"; payload = { files: openPaths }; break;
      default: console.error("Unknown Neutralino command action:", action); throw new Error(`Unsupported Neutralino action: ${action}`);
    }
  } catch (err) { console.error(`Error executing Neutralino action '${action}':`, err); payload = { message: err.message, details: err.toString() }; }

  if (window.IIA_Desktop_EmbeddedComms && window.IIA_Desktop_EmbeddedComms.sendMessageToServer) {
    sendNeutralinoResult(command_id, status, payload);
  } else {
    console.error("Cannot send Neutralino result: communication module not available.");
  }
}

function sendNeutralinoResult(command_id, status, result_payload) {
  const messageObject = { type: "NEUTRALINO_RESULT", content: { command_id: command_id, status: status, payload: result_payload } };
  window.IIA_Desktop_EmbeddedComms.sendMessageToServer(messageObject);
  appendMessage('system-message', `Sent result for NeutralinoBridge action ${command_id} (status: ${status})`);
}

// Neutralino Ready and Close events
Neutralino.events.on("ready", async () => {
    console.log("Neutralino ready. Initializing communication with embedded Python backend.");
    if (!document.getElementById('app')) {
        console.error("Main app element not found on ready. HTML might not be fully loaded.");
        return;
    }
    if (window.IIA_Desktop_EmbeddedComms && window.IIA_Desktop_EmbeddedComms.initCommunication) {
        try {
            await window.IIA_Desktop_EmbeddedComms.initCommunication();
        } catch (e) {
            updateStatus("ERROR: Failed to initialize Python backend communication.", true);
            console.error("Error during initCommunication:", e);
        }
    } else {
        updateStatus("ERROR: Communication module not loaded correctly.", true);
        console.error("IIA_Desktop_EmbeddedComms.initCommunication is not available.");
    }
});

// Define the primary onWindowClose handler that includes cleanup
async function onAppWindowClose() { // Renamed to avoid conflict if any global onWindowClose exists
  console.log("onAppWindowClose event triggered.");
  if (window.IIA_Desktop_EmbeddedComms && window.IIA_Desktop_EmbeddedComms.cleanupPythonProcess) {
    try {
      appendMessage('system-message', "Application closing. Cleaning up Python process...");
      updateStatus("Application closing...", false);
      await window.IIA_Desktop_EmbeddedComms.cleanupPythonProcess();
      console.log("Python process cleanup requested.");
    } catch (e) {
      console.error("Error during cleanupPythonProcess on window close:", e);
      appendMessage('error-message', "Error during cleanup on exit: " + e.message);
    }
  }
  // Allow some time for cleanup to attempt, then exit.
  // Neutralino.app.exit() should be called after async cleanup is done or timeout.
  // However, Neutralino's event model might exit before promise resolves fully.
  // Forcing a small delay can sometimes help, but not guaranteed.
  // setTimeout(() => {
  //   Neutralino.app.exit();
  // }, 500); // Not ideal, better if cleanupPythonProcess is faster or synchronous part of kill.
  Neutralino.app.exit(); // Call exit directly. CleanupPythonProcess sends kill signal.
}
Neutralino.events.on("windowClose", onAppWindowClose);


console.log("main.js updated for WebSocket-based file uploads.");
