# II-Agent API Reference

This document describes the **public Python API** of II-Agent.  
All modules live under the top-level package `ii_agent`.  Import paths shown below assume:

```python
from ii_agent import ...
```

---

## 1. Core Agent Layer

### 1.1 `BaseAgent`

| Location | `src/ii_agent/agents/base.py` |
|----------|------------------------------|

```python
class BaseAgent(ABC):
    llm_client: LLMClient
    tool_manager: ToolManager
    context_manager: ContextManagerProtocol

    def run(self, user_message: str) -> str: ...
    def _prepare_prompt(self, user_message: str) -> LLMRequest: ...
    def _extract_tool_calls(self, llm_response: LLMResponse) -> list[ToolCall]: ...
    def _handle_tool_results(
        self, tool_calls: list[ToolCall], results: list[ToolResult]
    ) -> None: ...
```

* **run** – one top-level interaction loop: build prompt → call LLM → execute tools → repeat.  
* **_prepare_prompt** – combine system prompt, history, & tool schemas.  
* **_extract_tool_calls** – parse function-call JSON from LLM response.  
* **_handle_tool_results** – append tool outputs to message history.

> **Usage**

```python
from ii_agent.agents.base import BaseAgent
from ii_agent.tools import ToolManager
from ii_agent.llm.anthropic import AnthropicClient
from ii_agent.llm.context_manager.llm_summarizing import LLMSummarizingContextManager

agent = BaseAgent(
    llm_client=AnthropicClient(api_key="..."),
    tool_manager=ToolManager.default(),
    context_manager=LLMSummarizingContextManager(),
)
answer = agent.run("Summarise the Industrial Revolution in 150 words.")
```

### 1.2 `AnthropicFC`

| Location | `src/ii_agent/agents/anthropic_fc.py` |
|----------|----------------------------------------|

Specialised subclass that uses **Claude Function-Calling**.

```python
class AnthropicFC(BaseAgent):
    model: str = "claude-3-7-sonnet"
    max_tokens: int = 4096

    def _prepare_prompt(...): ...
    def _extract_tool_calls(...): ...
```

*Accepts the same constructor as `BaseAgent` but defaults to Claude 3.7 Sonnet.*

---

## 2. LLM Clients

### Common Interface

```python
class LLMClient(Protocol):
    model: str
    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
        **kwargs
    ) -> LLMResponse: ...
```

### Concrete Implementations

| Client | File | Notes |
|--------|------|-------|
| **AnthropicClient** | `llm/anthropic.py` | Calls Anthropic HTTP API; supports function calling & streaming |
| **OpenAIClient** | `llm/openai.py` | Used by image/video tools; wraps `/v1/chat/completions` |
| **VertexAnthropicClient** | `llm/anthropic.py` (`vertex=True`) | Same interface, uses Google Vertex AI endpoint |

```python
from ii_agent.llm.anthropic import AnthropicClient

llm = AnthropicClient(api_key="...", model="claude-3-7-sonnet")
response = llm.complete([{"role": "user", "content": "Hello!"}])
print(response.content)
```

---

## 3. Context Managers

All implement `ContextManagerProtocol` (`llm/context_manager/base.py`).

### Available Managers

| Class | Strategy | Import |
|-------|----------|--------|
| `LLMSummarizingContextManager` | Summarises older turns via LLM | `llm.context_manager.llm_summarizing` |
| `AmortizedForgettingContextManager` | Drops least-recent turns by token-budget | `llm.context_manager.amortized_forgetting` |
| `PipelineContextManager` | Chains managers in order | `llm.context_manager.pipeline` |

```python
from ii_agent.llm.context_manager.pipeline import PipelineContextManager
ctx = PipelineContextManager([
    LLMSummarizingContextManager(summary_ratio=0.2),
    AmortizedForgettingContextManager(max_tokens=8000),
])
```

---

## 4. Tool System

### 4.1 `Tool` Base Class

| Location | `src/ii_agent/tools/base.py` |

```python
class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, ToolParam]

    def call(
        self,
        params: ToolCallParameters,
        workspace: WorkspaceManager,
        message_queue: MessageQueue | None = None
    ) -> ToolResult: ...
```

*Return value must be JSON-serialisable; large outputs are saved to workspace.*

### 4.2 `ToolManager`

| Location | `src/ii_agent/tools/tool_manager.py` |

```python
class ToolManager:
    def __init__(self, tools: list[Tool]): ...
    @classmethod
    def default(cls) -> "ToolManager": ...
    def register(self, tool: Tool) -> None: ...
    def get_schema(self) -> list[ToolSchema]: ...
    def dispatch(self, tool_call: ToolCall, workspace: WorkspaceManager) -> ToolResult: ...
```

> **Implementing a custom tool**

```python
from ii_agent.tools.base import Tool

class HelloTool(Tool):
    name = "hello_tool"
    description = "Say hello"
    parameters = {"name": {"type": "string", "description": "person"}}

    def call(self, params, workspace, **_):
        return {"content": f"Hello, {params['name']}!"}

# Register
tool_mgr = ToolManager.default()
tool_mgr.register(HelloTool())
```

---

## 5. Utilities

| Module | Purpose |
|--------|---------|
| `llm/token_counter.py` | Heuristic token counting for budgeting |
| `utils/workspace_manager.py` | Per-session file isolation & static URL mapping |
| `utils/prompt_generator.py` | Generates system & tool prompts |
| `utils/indent_utils.py` | Pretty-prints nested JSON for logs |

```python
from ii_agent.llm.token_counter import estimate_tokens
tokens = estimate_tokens("Hello world")
```

---

## 6. Browser Automation

### 6.1 `Browser`

| File | `src/ii_agent/browser/browser.py` |
|------|-----------------------------------|

```python
class Browser:
    def visit(self, url: str) -> str: ...
    def click(self, selector: str) -> None: ...
    def enter_text(self, selector: str, text: str) -> None: ...
    def scroll(self, amount: int = 1000) -> None: ...
    def screenshot(self) -> bytes: ...
```

Internally uses **Playwright Chromium** with a CV-based `Detector` (`browser/detector.py`) to find visible elements.

### 6.2 Browser Tool Suite

| Tool | Action |
|------|--------|
| `VisitWebpageTool` | Load page and save HTML |
| `BrowserClickElementTool` | Click element by text / CSS |
| `BrowserScrollTool` | Scroll viewport |
| `BrowserEnterTextTool` | Type into input |
| `ListHtmlLinksTool` | Extract list of `<a>` links |

All tools live under `tools/browser_tools/`.

---

## 7. Putting It Together – End-to-End Example

```python
from ii_agent.agents.anthropic_fc import AnthropicFC
from ii_agent.tools.tool_manager import ToolManager
from ii_agent.llm.context_manager.llm_summarizing import LLMSummarizingContextManager
from ii_agent.utils.workspace_manager import WorkspaceManager

workspace = WorkspaceManager(root="./workspace_demo")
agent = AnthropicFC(
    llm_client=AnthropicClient(api_key="..."),
    tool_manager=ToolManager.default(),
    context_manager=LLMSummarizingContextManager(max_tokens=12000),
    workspace_manager=workspace,
)

print(agent.run("Find the latest GDP growth rate of Japan, cite your source."))
```

---

## 8. Versioning & Stability

Public APIs listed here follow **semantic versioning**:

* **Minor** releases may add new optional parameters.
* **Major** releases may rename or remove classes/methods.

Check the [changelog](../CHANGELOG.md) for detailed history.

---

© Intelligent Internet – II-Agent is licensed under Apache 2.0.  
Feel free to extend and integrate; contributions are welcome!
