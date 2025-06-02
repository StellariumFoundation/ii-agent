"use client";

import { Terminal as XTerm } from "@xterm/xterm";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import {
  Code,
  Globe,
  Terminal as TerminalIcon,
  X,
  Loader2,
  Share,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { cloneDeep, debounce } from "lodash";
import dynamic from "next/dynamic";
import { Orbitron } from "next/font/google";
// import Cookies from "js-cookie"; // No longer needed for deviceId
import { v4 as uuidv4 } from "uuid"; // Still used for message IDs in handleEvent
import { useRouter, useSearchParams } from "next/navigation";
import SidebarButton from "@/components/sidebar-button";

import useNeutralinoAPI from '@/hooks/useNeutralinoAPI';

const orbitron = Orbitron({
  subsets: ["latin"],
});

import Browser from "@/components/browser";
import CodeEditor from "@/components/code-editor";
import QuestionInput from "@/components/question-input";
import SearchBrowser from "@/components/search-browser";
const Terminal = dynamic(() => import("@/components/terminal"), {
  ssr: false,
});
import { Button } from "@/components/ui/button";
import {
  ActionStep,
  AgentEvent,
  AVAILABLE_MODELS,
  IEvent,
  Message,
  TAB,
  TOOL,
} from "@/typings/agent";
import ChatMessage from "./chat-message";
import ImageBrowser from "./image-browser";

// Helper function
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

export default function Home() {
  const xtermRef = useRef<XTerm | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const searchParams = useSearchParams();
  const router = useRouter();
  const neuAPI = useNeutralinoAPI();

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [activeTab, setActiveTab] = useState(TAB.BROWSER);
  const [currentActionData, setCurrentActionData] = useState<ActionStep>();
  const [activeFileCodeEditor, setActiveFileCodeEditor] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [isCompleted, setIsCompleted] = useState(false);
  const [isStopped, setIsStopped] = useState(false);
  const [workspaceInfo, setWorkspaceInfo] = useState(""); // Session-specific workspace path
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [deviceId, setDeviceId] = useState<string>(""); // Now set from bootstrap
  const [sessionId, setSessionId] = useState<string | null>(null); // Set from CONNECTION_ESTABLISHED
  const [isLoadingSession, setIsLoadingSession] = useState(false); // For replay mode
  const [filesContent, setFilesContent] = useState<{ [key: string]: string }>({});
  const [browserUrl, setBrowserUrl] = useState("");
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [editingMessage, setEditingMessage] = useState<Message>();
  const [toolSettings, setToolSettings] = useState({
    deep_research: false,
    pdf: true,
    media_generation: true,
    audio_generation: true,
    browser: true,
    neutralino_bridge: true, // Enable NeutralinoBridgeTool by default for desktop
  });
  const [selectedModel, setSelectedModel] = useState<string>(AVAILABLE_MODELS[0]);

  const isReplayMode = useMemo(() => !!searchParams.get("id"), [searchParams]);

  // Session ID from URL (for replay mode)
  useEffect(() => {
    if (isReplayMode) {
      const id = searchParams.get("id");
      setSessionId(id);
    }
  }, [isReplayMode, searchParams]);

  // Fetch session events (for replay mode)
  useEffect(() => {
    const fetchSessionEvents = async () => {
      const id = searchParams.get("id");
      if (!id || !isReplayMode) return; // Only if in replay mode and id is present

      setIsLoadingSession(true);
      try {
        // This part is for fetching from an external server for replays.
        // Not applicable if Neutralino app is fully offline and doesn't have this server.
        if (!process.env.NEXT_PUBLIC_API_URL) {
            console.warn("NEXT_PUBLIC_API_URL not set, cannot fetch session history for replay.");
            toast.warn("Cannot fetch session history: API URL not configured.");
            setIsLoadingSession(false);
            return;
        }
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/sessions/${id}/events`);
        if (!response.ok) throw new Error(`Error fetching session events: ${response.statusText}`);
        const data = await response.json();
        setWorkspaceInfo(data.events?.[0]?.workspace_dir);
        if (data.events && Array.isArray(data.events)) {
          const processEventsWithDelay = async () => {
            setIsLoading(true);
            for (let i = 0; i < data.events.length; i++) {
              const event = data.events[i];
              await new Promise((resolve) => setTimeout(resolve, 50));
              handleEvent({ ...event.event_payload, id: event.id });
            }
            setIsLoading(false);
          };
          processEventsWithDelay();
        }
      } catch (error) {
        console.error("Failed to fetch session events:", error);
        toast.error("Failed to load session history");
      } finally {
        setIsLoadingSession(false);
      }
    };
    if (isReplayMode) fetchSessionEvents();
  }, [isReplayMode, searchParams]);


  // Load selected model from cookies (can remain)
  useEffect(() => {
    const savedModel = Cookies.get("selected_model");
    if (savedModel && AVAILABLE_MODELS.includes(savedModel)) { setSelectedModel(savedModel); }
    else { setSelectedModel(AVAILABLE_MODELS[0]); }
  }, []);


  // New WebSocket Connection Logic using Bootstrap
  useEffect(() => {
    let localWsInstance: WebSocket | null = null;
  
    const initializeAppConnection = async () => {
      if (isReplayMode) {
        console.log("Home.tsx: Replay mode, skipping WebSocket connection.");
        return;
      }
      if (socket) { // Check main socket state
          console.log("Home.tsx: WebSocket connection already exists or is being established by another effect.");
          return;
      }
  
      const bootstrapStatusDiv = document.getElementById('bootstrap-status');
      
      console.log("Home.tsx: Waiting for PYTHON_BACKEND_READY promise...");
      // Ensure window.PYTHON_BACKEND_READY is available
      if (!(window as any).PYTHON_BACKEND_READY) {
          console.error("Home.tsx: PYTHON_BACKEND_READY promise not found on window. Bootstrap script might have failed.");
          toast.error("Critical: Bootstrap script failed to initialize. Cannot connect to backend.");
          if (bootstrapStatusDiv) bootstrapStatusDiv.innerHTML += "<p style='color:red;'>ERROR: Bootstrap promise not found!</p>";
          return;
      }
      const backendConfig = await (window as any).PYTHON_BACKEND_READY;
  
      if (!backendConfig || !backendConfig.success) {
        const errorMsg = `Embedded Python backend failed: ${backendConfig?.error?.message || backendConfig?.error || 'Unknown error'}`;
        toast.error(errorMsg);
        console.error("Home.tsx: Python backend did not initialize successfully.", backendConfig?.error);
        if (bootstrapStatusDiv) bootstrapStatusDiv.innerHTML += `<p style='color:red;'>${errorMsg}</p>`;
        // Do not remove bootstrapStatusDiv on error, so user can see the message.
        return;
      }
      
      if (bootstrapStatusDiv) bootstrapStatusDiv.style.display = 'none'; // Hide on successful backend ready signal
  
      const embeddedPort = backendConfig.port;
      const resolvedDeviceIdFromBootstrap = backendConfig.deviceId;
  
      if (!resolvedDeviceIdFromBootstrap) {
        toast.error("Device ID not provided by bootstrap. Cannot connect WebSocket.");
        console.error("Home.tsx: Device ID missing from bootstrap config.");
        return;
      }
      setDeviceId(resolvedDeviceIdFromBootstrap); 
  
      const params = new URLSearchParams({ device_id: resolvedDeviceIdFromBootstrap });
      const wsUrl = `ws://localhost:${embeddedPort}?${params.toString()}`;
      
      console.log(`Home.tsx: Connecting to embedded Python backend at: ${wsUrl}`);
      toast.info(`Connecting to backend...`);
  
      localWsInstance = new WebSocket(wsUrl);
      // setSocket(localWsInstance); // Set socket state immediately for access in handlers

      localWsInstance.onopen = () => {
        console.log("Home.tsx: WebSocket connection established with embedded backend.");
        toast.success("Connected to II-Agent backend.");
        setSocket(localWsInstance); // Set socket state now that it's open
        if (localWsInstance && localWsInstance.readyState === WebSocket.OPEN) {
          localWsInstance.send(
            JSON.stringify({
              type: AgentEvent.INIT_AGENT,
              content: {
                model_name: selectedModel || AVAILABLE_MODELS[0],
                tool_args: toolSettings,
              },
            })
          );
          console.log("Home.tsx: Sent INIT_AGENT to embedded backend.");
        }
      };
  
      localWsInstance.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === AgentEvent.CONNECTION_ESTABLISHED) {
              if (data.content && data.content.session_uuid) {
                  setSessionId(data.content.session_uuid);
                  console.log("Home.tsx: Session UUID from embedded backend:", data.content.session_uuid);
              }
              if (data.content && data.content.workspace_path) {
                  setWorkspaceInfo(data.content.workspace_path);
              }
          }
          handleEvent({ ...data, id: data.id || uuidv4() });
        } catch (error) { 
            console.error("Home.tsx: Error parsing WebSocket data:", error);
            toast.error("Received malformed data from backend.");
        }
      };
  
      localWsInstance.onerror = (errorEvent) => { 
          console.error("Home.tsx: WebSocket error:", errorEvent);
          toast.error("WebSocket connection error. Check console or bootstrap status panel.");
          // Update bootstrap status as well if it's still visible
          const bsDiv = document.getElementById('bootstrap-status');
          if (bsDiv && bsDiv.style.display !== 'none') {
            bsDiv.innerHTML += `<p style='color:red;'>WebSocket connection error. Backend might be down.</p>`;
          }
      };
      localWsInstance.onclose = (event) => { 
          console.log(`Home.tsx: WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
          setSocket(null); // Clear the main socket state
          if (event.code !== 1000 && event.code !== 1005) { // 1000 = Normal, 1005 = No Status Recvd (often normal on app close)
            toast.info(`Disconnected from II-Agent backend (Code: ${event.code})`);
          }
      };
    };
  
    if (!isReplayMode && !socket) { 
      initializeAppConnection();
    }
  
    return () => {
      if (localWsInstance && localWsInstance.readyState === WebSocket.OPEN) {
        console.log("Home.tsx: Closing WebSocket on effect cleanup.");
        localWsInstance.close(1000, "Effect cleanup");
      }
    };
  }, [isReplayMode, selectedModel, toolSettings, socket]); // Added selectedModel, toolSettings, socket to dependencies


  const localAppendMessage = (role: Message['role'], text: string, id?: string) => { /* ... as previously defined ... */ 
    const newMessage: Message = { id: id || `local-${Date.now().toString()}`, role: role, content: text, timestamp: Date.now() };
    setMessages(prev => [...prev, newMessage]);
  };
  const handleFileUpload = async () => { /* ... as previously defined ... */ 
    if (!neuAPI.isNeutralinoAvailable) { toast.error("File uploads only in desktop app."); return; }
    if (!socket || socket.readyState !== WebSocket.OPEN) { toast.error("WebSocket not open. Cannot upload."); return; }
    try {
      const selectedFilePaths = await neuAPI.os.showOpenDialog("Select file(s)", {});
      let filesToUpload: string[] = [];
      if (typeof selectedFilePaths === 'string' && selectedFilePaths) filesToUpload = [selectedFilePaths];
      else if (Array.isArray(selectedFilePaths)) filesToUpload = selectedFilePaths;
      if (!filesToUpload || filesToUpload.length === 0) return;
      setIsUploading(true);
      const fileNamesOnly = filesToUpload.map(fp => fp.split(/[/\\]/).pop() || 'unknown');
      localAppendMessage("user", `Preparing to upload: ${fileNamesOnly.join(', ')}`, `upload-prep-${Date.now()}`);
      for (const filePath of filesToUpload) {
        const fileName = filePath.split(/[/\\]/).pop() || 'unknown_file';
        localAppendMessage("system", `Processing ${fileName}...`);
        let fileContentForUpload;
        const fileExtension = fileName.split('.').pop()?.toLowerCase() || '';
        const textExtensions = ['txt', 'md', 'json', 'py', 'js', 'html', 'css', 'csv', 'xml', 'log', 'sh', 'java', 'c', 'cpp', 'h', 'hpp', 'rb', 'php', 'pl', 'yaml', 'ini', 'toml', 'rtf', 'tex', 'sql'];
        try {
          if (textExtensions.includes(fileExtension)) {
            try {
              const textContent = await neuAPI.filesystem.readFile(filePath);
              const tempArrayBuffer = new TextEncoder().encode(textContent);
              fileContentForUpload = `data:text/plain;base64,${arrayBufferToBase64(tempArrayBuffer)}`;
            } catch (e) {
              console.warn(`Read ${fileName} as text failed, trying binary:`, e);
              const binaryContent = await neuAPI.filesystem.readBinaryFile(filePath);
              fileContentForUpload = `data:application/octet-stream;base64,${arrayBufferToBase64(binaryContent)}`;
            }
          } else {
            const binaryContent = await neuAPI.filesystem.readBinaryFile(filePath);
            fileContentForUpload = `data:application/octet-stream;base64,${arrayBufferToBase64(binaryContent)}`;
          }
          const uploadRequestMessage = { type: AgentEvent.FILE_UPLOAD_REQUEST, content: { fileName: fileName, fileContent: fileContentForUpload } };
          if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(uploadRequestMessage));
            localAppendMessage("system", `Upload request for ${fileName} sent.`);
          } else { throw new Error("WebSocket not open for upload."); }
        } catch (err: any) {
          console.error(`Error processing/sending ${fileName}:`, err);
          toast.error(`Failed to process/send ${fileName}: ${err.message}`);
          localAppendMessage("error", `Failed to upload ${fileName}: ${err.message}`);
        }
      }
    } catch (err: any) {
      console.error("File selection/Neutralino API error:", err);
      if (err.code !== 'NE_OS_NOFLCH' && err.message && !err.message.toLowerCase().includes("cancelled")) { toast.error(`File selection error: ${err.message}`); }
    } finally { setIsUploading(false); }
  };

  const handleEnhancePrompt = () => { /* ... as previously defined ... */ };
  const handleClickAction = debounce((data: ActionStep | undefined, showTabOnly = false) => { /* ... as previously defined ... */ }, 50);
  const handleQuestionSubmit = async (newQuestion: string) => { /* ... as previously defined, ensure it uses 'socket' state ... */ 
    if (!newQuestion.trim() || isLoading) return;
    setIsLoading(true); setCurrentQuestion(""); setIsCompleted(false); setIsStopped(false);
    const newUserMessage: Message = { id: Date.now().toString(), role: "user", content: newQuestion, timestamp: Date.now() };
    setMessages((prev) => [...prev, newUserMessage]);
    if (!socket || socket.readyState !== WebSocket.OPEN) { toast.error("WebSocket not open."); setIsLoading(false); return; }
    socket.send( JSON.stringify({ type: "query", content: { text: newQuestion, resume: messages.length > 1, files: uploadedFiles } }) );
  };
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => { /* ... as previously defined ... */ };
  const resetChat = () => { /* ... as previously defined ... */ };
  const handleOpenVSCode = () => { /* ... as previously defined ... */ };
  const parseJson = (jsonString: string) => { /* ... as previously defined ... */ };
  const handleEditMessage = (newQuestion: string) => { /* ... as previously defined ... */ };
  const getRemoteURL = (path: string | undefined) => { /* ... as previously defined ... */ };

  async function executeNeutralinoCommandFromAgent(commandData: any) { /* ... as previously defined ... */ 
    if (!neuAPI.isNeutralinoAvailable) { console.warn("Neutralino API not available for agent cmd:", commandData); sendNeutralinoResultToBackend(commandData.command_id, "error", { message: "Neutralino API not available." }); return; }
    const { command_id, action, details } = commandData; let status = "error"; let payload: any = {};
    console.log(`React: Executing Agent Neutralino Cmd: ${action}`, details); localAppendMessage("system", `Agent desktop cmd: ${action} ${JSON.stringify(details)}`);
    try {
      switch (action) {
        case 'show_notification': if (!details || !details.title || !details.content) throw new Error("Missing params for notification."); await neuAPI.os.showNotification(details.title, details.content, details.icon || 'INFO'); status = "success"; payload = { message: "Notification shown." }; break;
        case 'show_save_dialog': if (!details || !details.title) throw new Error("Missing title for save dialog."); const savePath = await neuAPI.os.showSaveDialog(details.title, { defaultPath: details.defaultPath || '' }); status = "success"; payload = { filePath: savePath }; break;
        case 'show_open_dialog': if (!details || !details.title) throw new Error("Missing title for open dialog."); const openPaths = await neuAPI.os.showOpenDialog(details.title, { defaultPath: details.defaultPath || '', multiSelections: details.multiSelections || false }); status = "success"; payload = { files: openPaths }; break;
        default: throw new Error(`Unsupported Neutralino action from agent: ${action}`);
      }
    } catch (err: any) { console.error(`Error exec agent Neutralino action '${action}':`, err); payload = { message: err.message, code: err.code, details: err.toString() }; status = "error"; }
    sendNeutralinoResultToBackend(command_id, status, payload);
  }
  function sendNeutralinoResultToBackend(command_id: string, status: string, result_payload: any) { /* ... as previously defined, ensure it uses 'socket' state ... */ 
    if (!socket || socket.readyState !== WebSocket.OPEN) { console.error("WS not open for Neutralino result."); toast.error("Cannot send desktop result: WS disconnected."); return; }
    const messageObject = { type: AgentEvent.NEUTRALINO_RESULT, content: { command_id: command_id, status: status, payload: result_payload } };
    socket.send(JSON.stringify(messageObject)); localAppendMessage("system", `Sent result for desktop cmd ${command_id} (status: ${status}) to agent.`);
  }

  const handleEvent = (data: { id: string; type: AgentEvent; content: Record<string, unknown>; }) => {
    // Ensure this uses the AgentEvent enum correctly after agent.ts changes
    // Specifically AgentEvent.FILE_UPLOAD_SUCCESS and AgentEvent.FILE_UPLOAD_FAILURE
    // And AgentEvent.NEUTRALINO_COMMAND and AgentEvent.NEUTRALINO_RESULT
    switch (data.type) {
      case AgentEvent.USER_MESSAGE: /* ... */ setMessages((prev) => [ ...prev, { id: data.id, role: "user", content: data.content.text as string, timestamp: Date.now() } ]); break;
      case AgentEvent.PROMPT_GENERATED: /* ... */ setIsGeneratingPrompt(false); setCurrentQuestion(data.content.result as string); break;
      case AgentEvent.PROCESSING: /* ... */ setIsLoading(true); break;
      case AgentEvent.WORKSPACE_INFO: /* ... */ setWorkspaceInfo(data.content.path as string); break;
      case AgentEvent.AGENT_THINKING: /* ... */ setMessages((prev) => [ ...prev, { id: data.id, role: "assistant", content: data.content.text as string, timestamp: Date.now() } ]); break;
      case AgentEvent.TOOL_CALL: /* ... (existing logic) ... */ 
        const tool_message: Message = { id: data.id, role: "assistant", action: { type: data.content.tool_name as TOOL, data: data.content, }, timestamp: Date.now(), };
        const tool_url = (data.content.tool_input as { url: string })?.url as string;
        if (tool_url) { setBrowserUrl(tool_url); }
        setMessages((prev) => [...prev, tool_message]);
        handleClickAction(tool_message.action);
        break;
      case AgentEvent.FILE_EDIT: /* ... */ break;
      case AgentEvent.BROWSER_USE: /* ... */ break;
      case AgentEvent.TOOL_RESULT: /* ... (existing logic) ... */ 
        setMessages((prev) => {
            const lastMessage = cloneDeep(prev[prev.length - 1]);
            if (lastMessage?.action && lastMessage.action?.type === data.content.tool_name) {
                lastMessage.action.data.result = `${data.content.result}`;
                lastMessage.action.data.isResult = true;
                setTimeout(() => { handleClickAction(lastMessage.action); }, 500);
                return [...prev.slice(0, -1), lastMessage];
            } // else, it's a new message or unassociated result
            return [...prev, { id: data.id, role: "assistant", content: `Tool result for ${data.content.tool_name}: ${JSON.stringify(data.content.result)}`, timestamp: Date.now() }];
        });
        break;
      case AgentEvent.AGENT_RESPONSE: /* ... */ setMessages((prev) => [ ...prev, { id: Date.now().toString(), role: "assistant", content: data.content.text as string, timestamp: Date.now() } ]); setIsCompleted(true); setIsLoading(false); break;
      case AgentEvent.FILE_UPLOAD_SUCCESS: 
        toast.success(`File '${data.content.originalName}' uploaded to ${data.content.filePathInWorkspace}`);
        localAppendMessage("system", `File '${data.content.originalName}' uploaded. Path: ${data.content.filePathInWorkspace}. Ask agent to use it.`, data.id || `fs-${Date.now()}`);
        setUploadedFiles((prev) => [...prev, data.content.filePathInWorkspace as string]); 
        if(neuAPI.isNeutralinoAvailable) neuAPI.os.showNotification('Upload Successful', `'${data.content.originalName}' uploaded.`);
        setIsUploading(false); break;
      case AgentEvent.FILE_UPLOAD_FAILURE:
        toast.error(`Upload failed for '${data.content.originalName}': ${data.content.message}`);
        localAppendMessage("error", `File upload failed for '${data.content.originalName}': ${data.content.message}`, data.id || `fe-${Date.now()}`);
        if(neuAPI.isNeutralinoAvailable) neuAPI.os.showNotification('Upload Failed', data.content.message as string);
        setIsUploading(false); break;
      case AgentEvent.ERROR: 
        toast.error(data.content.message as string); setIsUploading(false); setIsLoading(false); break;
      case AgentEvent.NEUTRALINO_COMMAND:
        executeNeutralinoCommandFromAgent(data.content); break;
      case AgentEvent.NEUTRALINO_RESULT:
        localAppendMessage("system", `Desktop action result for ${data.content.command_id}: ${data.content.status}`); break;
      default: console.warn("Unhandled event type in Home.tsx handleEvent:", data.type, data);
    }
  };

  const isBrowserTool = useMemo( () => { /* ... as previously defined ... */ return false; }, [currentActionData] );
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages?.length]);

  return ( /* ... existing JSX ... */ 
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#191E1B]">
      <SidebarButton />
      {!isInChatView && ( <Image src="/logo-only.png" alt="II-Agent Logo" width={80} height={80} className="rounded-sm" /> )}
      <div className={`flex justify-between w-full ${ !isInChatView ? "pt-0 pb-8" : "p-4" }`} >
        {!isInChatView && <div />}
        <motion.h1 className={`font-semibold text-center ${ isInChatView ? "flex items-center gap-x-2 text-2xl" : "text-4xl" } ${orbitron.className}`} layout layoutId="page-title" >
          {isInChatView && ( <Image src="/logo-only.png" alt="II-Agent Logo" width={40} height={40} className="rounded-sm" /> )}
          {`II-Agent`}
        </motion.h1>
        {isInChatView ? (
          <div className="flex gap-x-2">
            <Button className="cursor-pointer h-10" variant="outline" onClick={handleShare}> <Share /> Share </Button>
            <Button className="cursor-pointer" onClick={resetChat}> <X className="size-5" /> </Button>
          </div>
        ) : ( <div /> )}
      </div>
      {isLoadingSession ? (
        <div className="flex flex-col items-center justify-center p-8">
          <Loader2 className="h-8 w-8 text-white animate-spin mb-4" />
          <p className="text-white text-lg">Loading session history...</p>
        </div>
      ) : (
        <LayoutGroup>
          <AnimatePresence mode="wait">
            {!isInChatView ? (
              <QuestionInput
                placeholder="Give II-Agent a task to work on..."
                value={currentQuestion}
                setValue={setCurrentQuestion}
                handleKeyDown={handleKeyDown}
                handleSubmit={handleQuestionSubmit}
                handleFileUpload={handleFileUpload} 
                isUploading={isUploading}
                isDisabled={!socket || socket.readyState !== WebSocket.OPEN}
                isGeneratingPrompt={isGeneratingPrompt}
                handleEnhancePrompt={handleEnhancePrompt}
                toolSettings={toolSettings}
                setToolSettings={setToolSettings}
                selectedModel={selectedModel}
                setSelectedModel={setSelectedModel}
              />
            ) : (
              <motion.div key="chat-view" initial={{ opacity: 0, y: 30, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -20, scale: 0.95 }} transition={{ type: "spring", stiffness: 300, damping: 30, mass: 1, }} className="w-full grid grid-cols-10 write-report overflow-hidden flex-1 pr-4 pb-4 " >
                <ChatMessage messages={messages} isLoading={isLoading} isCompleted={isCompleted} isStopped={isStopped} workspaceInfo={workspaceInfo} handleClickAction={handleClickAction} isUploading={isUploading} isReplayMode={isReplayMode} currentQuestion={currentQuestion} messagesEndRef={messagesEndRef} setCurrentQuestion={setCurrentQuestion} handleKeyDown={handleKeyDown} handleQuestionSubmit={handleQuestionSubmit} handleFileUpload={handleFileUpload} isGeneratingPrompt={isGeneratingPrompt} handleEnhancePrompt={handleEnhancePrompt} handleCancel={handleCancelQuery} editingMessage={editingMessage} setEditingMessage={setEditingMessage} handleEditMessage={handleEditMessage} />
                <div className="col-span-6 bg-[#1e1f23] border border-[#3A3B3F] p-4 rounded-2xl">
                  <div className="pb-4 bg-neutral-850 flex items-center justify-between">
                    <div className="flex gap-x-4">
                      <Button className={`cursor-pointer hover:!bg-black ${ activeTab === TAB.BROWSER ? "bg-gradient-skyblue-lavender !text-black" : "" }`} variant="outline" onClick={() => setActiveTab(TAB.BROWSER)} > <Globe className="size-4" /> Browser </Button>
                      <Button className={`cursor-pointer hover:!bg-black ${ activeTab === TAB.CODE ? "bg-gradient-skyblue-lavender !text-black" : "" }`} variant="outline" onClick={() => setActiveTab(TAB.CODE)} > <Code className="size-4" /> Code </Button>
                      <Button className={`cursor-pointer hover:!bg-black ${ activeTab === TAB.TERMINAL ? "bg-gradient-skyblue-lavender !text-black" : "" }`} variant="outline" onClick={() => setActiveTab(TAB.TERMINAL)} > <TerminalIcon className="size-4" /> Terminal </Button>
                    </div>
                    <Button className="cursor-pointer" variant="outline" onClick={handleOpenVSCode} > <Image src={"/vscode.png"} alt="VS Code" width={20} height={20} /> Open with VS Code </Button>
                  </div>
                  <Browser className={ activeTab === TAB.BROWSER && (currentActionData?.type === TOOL.VISIT || isBrowserTool) ? "" : "hidden" } url={currentActionData?.data?.tool_input?.url || browserUrl} screenshot={ isBrowserTool ? (currentActionData?.data.result as string) : undefined } raw={ currentActionData?.type === TOOL.VISIT ? (currentActionData?.data?.result as string) : undefined } />
                  <SearchBrowser className={ activeTab === TAB.BROWSER && currentActionData?.type === TOOL.WEB_SEARCH ? "" : "hidden" } keyword={currentActionData?.data.tool_input?.query} search_results={ currentActionData?.type === TOOL.WEB_SEARCH && currentActionData?.data?.result ? parseJson(currentActionData?.data?.result as string) : undefined } />
                  <ImageBrowser className={ activeTab === TAB.BROWSER && currentActionData?.type === TOOL.IMAGE_GENERATE ? "" : "hidden" } url={currentActionData?.data.tool_input?.output_filename} image={getRemoteURL( currentActionData?.data.tool_input?.output_filename )} />
                  <CodeEditor currentActionData={currentActionData} activeTab={activeTab} className={activeTab === TAB.CODE ? "" : "hidden"} workspaceInfo={workspaceInfo} activeFile={activeFileCodeEditor} setActiveFile={setActiveFileCodeEditor} filesContent={filesContent} isReplayMode={isReplayMode} />
                  <Terminal ref={xtermRef} className={activeTab === TAB.TERMINAL ? "" : "hidden"} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </LayoutGroup>
      )}
    </div>
  );
}
