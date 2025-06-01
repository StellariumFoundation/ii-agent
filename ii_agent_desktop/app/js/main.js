// In ii_agent_desktop/app/js/main.js

// Initialize Neutralinojs
Neutralino.init();

function onWindowClose() {
  Neutralino.app.exit();
}
Neutralino.events.on("windowClose", onWindowClose);

// Global variable for session UUID
let currentSessionUUID = null;

// UI Elements
const queryInput = document.getElementById('query-input');
const sendButton = document.getElementById('send-button');
const messagesDiv = document.getElementById('messages');
const rawEventsDiv = document.getElementById('raw-events');
const statusDiv = document.getElementById('status');
const uploadFileButton = document.getElementById('upload-file-button');

// Event Listeners
sendButton.addEventListener('click', () => {
  const queryText = queryInput.value.trim();
  if (queryText) {
    sendMessageToServer({ type: 'query', content: { text: queryText, resume: false, files: [] } });
    appendMessage('user-message', `You: ${queryText}`);
    queryInput.value = '';
  }
});

queryInput.addEventListener('keypress', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendButton.click();
  }
});

// Helper to append to raw events log
function logRawEvent(eventData) {
  const currentText = rawEventsDiv.textContent;
  rawEventsDiv.textContent = `${currentText}
${JSON.stringify(eventData, null, 2)}`;
  rawEventsDiv.scrollTop = rawEventsDiv.scrollHeight;
}

// Helper to append formatted messages to the chat
function appendMessage(cssClass, textOrHtml, isHtml = false) {
  const messageElement = document.createElement('div');
  messageElement.classList.add('message', cssClass);
  if (isHtml) {
    messageElement.innerHTML = textOrHtml;
  } else {
    messageElement.textContent = textOrHtml;
  }
  messagesDiv.appendChild(messageElement);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Update status function
function updateStatus(message, isError = false) {
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

// File Upload Logic
async function selectAndUploadFile() {
  if (!currentSessionUUID) {
    updateStatus('Error: Session not established. Cannot upload file.', true);
    Neutralino.os.showNotification('Error', 'Session not established. Please connect to the agent first.');
    return;
  }

  try {
    const dialogOptions = {
      title: 'Select a file to upload',
    };
    const selectedEntries = await Neutralino.os.showOpenDialog(dialogOptions.title, dialogOptions);

    if (selectedEntries && selectedEntries.length > 0) {
      const filePath = selectedEntries[0];
      const fileName = filePath.split(/[/\\]/).pop();

      updateStatus(`Uploading ${fileName}...`);
      appendMessage('system-message', `Attempting to upload: ${fileName}`);

      let fileContent;
      let isBinary = false;
      const fileExtension = fileName.split('.').pop().toLowerCase();

      const textExtensions = ['txt', 'md', 'json', 'py', 'js', 'html', 'css', 'csv', 'xml', 'log'];
      if (textExtensions.includes(fileExtension)) {
        try {
            fileContent = await Neutralino.filesystem.readFile(filePath);
            isBinary = false;
        } catch (e) {
            console.warn(`Reading ${fileName} as text failed, trying binary: ${e.message}`);
            fileContent = await Neutralino.filesystem.readBinaryFile(filePath);
            isBinary = true;
        }
      } else {
        fileContent = await Neutralino.filesystem.readBinaryFile(filePath);
        isBinary = true;
      }

      let contentToSend;
      if (isBinary) {
        contentToSend = `data:application/octet-stream;base64,${arrayBufferToBase64(fileContent)}`;
      } else {
        contentToSend = fileContent;
      }

      const payload = {
        session_id: currentSessionUUID,
        file: {
          path: fileName,
          content: contentToSend
        }
      };

      const uploadUrl = 'http://localhost:8000/api/upload';

      const response = await fetch(uploadUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json();

      if (response.ok && result.file && result.file.path) {
        updateStatus(`File ${fileName} uploaded successfully as ${result.file.path} (workspace path).`);
        appendMessage('system-message', `File uploaded: ${fileName} (available at workspace path: ${result.file.path}). You can now instruct the agent to use it.`);
      } else {
        throw new Error(result.error || `Failed to upload file. Status: ${response.status}`);
      }
    }
  } catch (err) {
    console.error('File Upload Error:', err);
    updateStatus(`Error uploading file: ${err.message}`, true);
    appendMessage('error-message', `Failed to upload file: ${err.message}`);
    try {
        await Neutralino.os.showNotification('Upload Failed', `Could not upload file: ${err.message}`);
    } catch (notifyError) {
        console.error("Neutralino notification error:", notifyError);
    }
  }
}

if (uploadFileButton) {
  uploadFileButton.addEventListener('click', selectAndUploadFile);
} else {
  console.error("Upload file button element not found. Check ID in index.html.");
}

// Centralized RealtimeEvent handler
function handleRealtimeEvent(eventData) {
  const type = eventData.type;
  const content = eventData.content;

  console.log(`Handling event: ${type}`, content);

  switch (type) {
    case 'user_message':
      appendMessage('user-message', `User: ${content.text}`);
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
      } else {
        toolInputHtml += `<li>${JSON.stringify(content.tool_input, null, 2)}</li>`;
      }
      toolInputHtml += '</ul>';
      appendMessage('tool-call-message', `<strong>Tool Call: ${content.tool_name}</strong>${toolInputHtml}`, true);
      break;
    case 'tool_result':
      let resultText = content.result;
      try {
        if (typeof resultText === 'string') {
          const parsedJson = JSON.parse(resultText); // Try to parse if it's a JSON string
          resultText = JSON.stringify(parsedJson, null, 2); // Pretty print
        } else if (typeof resultText === 'object') {
          resultText = JSON.stringify(resultText, null, 2); // Pretty print if it's an object
        }
      } catch (e) {
        // Not a JSON string or already formatted, leave as is
      }
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
      updateStatus(`Connected. Session: ${currentSessionUUID}`);
      appendMessage('system-message', `Connection established. Workspace: ${content.workspace_path}. Session: ${currentSessionUUID}`);
      break;
    case 'agent_initialized':
      updateStatus("Agent initialized and ready.");
      appendMessage('system-message', 'Agent initialized and ready.');
      break;

    // New case for Neutralino Bridge Commands (Phase 4)
    case 'NEUTRALINO_COMMAND': // Ensure this string matches EventType.NEUTRALINO_COMMAND.value in Python
      console.log("Received NEUTRALINO_COMMAND:", content);
      executeNeutralinoCommand(content); // Call the new function
      break;

    default:
      console.warn('Received unhandled event type:', type, content);
  }
}

// New function to execute Neutralino commands (Phase 4)
async function executeNeutralinoCommand(commandData) {
  const { command_id, action, details } = commandData;
  let status = "error"; // Default to error
  let payload = {};

  appendMessage('system-message', `Executing desktop action: ${action}`);

  try {
    switch (action) {
      case 'show_notification':
        if (!details || typeof details.title !== 'string' || typeof details.content !== 'string') {
            throw new Error("Missing or invalid title/content for show_notification.");
        }
        await Neutralino.os.showNotification(details.title, details.content);
        status = "success";
        payload = { message: "Notification shown." };
        break;

      case 'show_save_dialog':
        if (!details || typeof details.title !== 'string') {
            throw new Error("Missing or invalid title for show_save_dialog.");
        }
        const savePath = await Neutralino.os.showSaveDialog(details.title, {
            defaultPath: details.defaultPath || ''
        });
        status = "success";
        payload = { filePath: savePath }; // savePath can be empty if user cancels
        break;

      case 'show_open_dialog':
        if (!details || typeof details.title !== 'string') {
            throw new Error("Missing or invalid title for show_open_dialog.");
        }
        const openPaths = await Neutralino.os.showOpenDialog(details.title, {
            defaultPath: details.defaultPath || '',
            multiSelections: details.multiSelections || false
        });
        status = "success";
        payload = { files: openPaths }; // openPaths is an array, can be empty
        break;

      default:
        console.error("Unknown Neutralino command action:", action);
        throw new Error(`Unsupported Neutralino action: ${action}`);
    }
  } catch (err) {
    console.error(`Error executing Neutralino action '${action}':`, err);
    payload = { message: err.message, details: err.toString() };
    // status remains 'error'
  }

  sendNeutralinoResult(command_id, status, payload);
}

// New function to send results of Neutralino commands back to backend (Phase 4)
function sendNeutralinoResult(command_id, status, result_payload) {
  const messageObject = {
    type: "NEUTRALINO_RESULT", // Ensure this string matches EventType.NEUTRALINO_RESULT.value in Python
    content: {
      command_id: command_id,
      status: status,
      payload: result_payload
    }
  };
  // Assumes sendMessageToServer is globally available from communication.js
  sendMessageToServer(messageObject);
  appendMessage('system-message', `Sent result for desktop action ${command_id} (status: ${status})`);
}

// Initialize Communication (defined in communication.js)
initCommunication();

console.log("main.js enhanced for Phase 4: NeutralinoBridgeTool frontend handling.");
