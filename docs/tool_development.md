# Tool Development Guide

This guide walks you through building **custom tools** for II-Agent—from the simplest “Hello” example to browser automation and advanced multimodal utilities.

---

## 1. Why Tools?

Tools extend the agent beyond pure text generation.  
When the LLM decides a task requires real-world interaction, it emits a **function-call** referencing a tool. II-Agent executes the tool, captures its result, and feeds it back to the LLM, allowing iterative reasoning.

```
LLM → "call bash_tool(command='ls')"  ──▶ Tool executes
                                 ▲◀── Result: "src\nREADME.md"
```

---

## 2. Tool Architecture

```
┌────────────────┐
│  BaseAgent     │
└──────┬─────────┘
       │ requests tool schema
┌──────▼─────────┐
│  ToolManager   │  ← registry & dispatcher
└──────┬─────────┘
   call│
┌──────▼─────────┐
│   Tool (Your   │  ← subclass per capability
│   Implementation)│
└────────────────┘
```

* `ToolManager` holds a list of **Tool** instances and exposes JSON schemas to the LLM.
* Each Tool subclasses `ii_agent.tools.base.Tool`.

---

## 3. Base Class Overview

File: `src/ii_agent/tools/base.py`

```python
class Tool(ABC):
    # Metadata
    name: str
    description: str
    parameters: dict[str, ToolParam]  # JSON schema

    # Main entry-point
    @abstractmethod
    def call(
        self,
        params: ToolCallParameters,
        workspace: WorkspaceManager,
        message_queue: MessageQueue | None = None
    ) -> ToolResult: ...
```

### Key Concepts

| Attribute | Purpose |
|-----------|---------|
| `name` | Unique identifier used in LLM function-call. |
| `description` | One-line human-readable summary. |
| `parameters` | JSON-schema dict describing accepted fields. |
| `call()` | Executes the capability and **returns serialisable data** (dict / str). |

---

## 4. Parameter Schemas

Parameters follow the [JSON Schema Draft-07](https://json-schema.org/) subset accepted by Claude/OpenAI function calling.

```python
parameters = {
    "name": {
        "type": "object",
        "properties": {
            "url":  {"type": "string", "description": "Target URL"},
            "wait": {"type": "integer", "description": "Wait ms after load"},
        },
        "required": ["url"]
    }
}
```

*Use `type`, `description`, `enum`, `minimum`, etc. to guide the LLM.*

---

## 5. Examples

### 5.1 Minimal “Hello” Tool

```python
# src/ii_agent/tools/hello_tool.py
from ii_agent.tools.base import Tool, ToolResult

class HelloTool(Tool):
    name = "hello_tool"
    description = "Greet a person."
    parameters = {
        "name": {
            "type": "object",
            "properties": {
                "person": {"type": "string", "description": "Name to greet"}
            },
            "required": ["person"]
        }
    }

    def call(self, params, *_):
        return ToolResult(content=f"Hello, {params['person']}!")
```

### 5.2 File-Processing Tool

```python
# Count lines in a workspace file
class LineCountTool(Tool):
    name = "count_lines"
    description = "Count lines of a text file stored in workspace."
    parameters = {
        "name": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path"}
            },
            "required": ["path"]
        }
    }

    def call(self, params, workspace, **_):
        abs_path = workspace.resolve(params["path"])
        with open(abs_path) as f:
            num = sum(1 for _ in f)
        return ToolResult(content=num)
```

### 5.3 Complex Browser Tool

Browser tools inherit `BrowserToolBase` (see `tools/browser_tools/base.py`) but conceptually:

```python
class BrowserClickElementTool(Tool):
    ...
    def call(self, params, workspace, **_):
        browser = workspace.get_browser()        # Playwright wrapper
        browser.click(params["selector"])
        screenshot_path = browser.screenshot()
        return ToolResult(
            content=f"Clicked {params['selector']}",
            files=[screenshot_path]              # Auto-deployed
        )
```

*Returned files are copied into the session workspace and served at `STATIC_FILE_BASE_URL`.*

---

## 6. Registering Your Tool

```python
from ii_agent.tools.tool_manager import ToolManager
from ii_agent.tools.hello_tool import HelloTool

tool_manager = ToolManager.default()
tool_manager.register(HelloTool())
```

*If you want it available everywhere, add the import + append to `DEFAULT_TOOLS` inside `src/ii_agent/tools/__init__.py`.*

---

## 7. Testing Tools

1. **Unit Test**

```python
def test_hello_tool():
    tool = HelloTool()
    res = tool.call({"person": "Ada"}, workspace=MockWorkspace())
    assert res.content == "Hello, Ada!"
```

2. **Integration**

Launch CLI with `--needs-permission false` and prompt:

```
Use hello_tool to greet Alan.
```

Verify streamed tool call & result.

---

## 8. Browser Tool Patterns

| Pattern | Module | Tip |
|---------|--------|-----|
| Visit → Click → Scroll | `visit_webpage_tool.py`, `browser_tools.click.py`, `browser_tools.scroll.py` | Compose calls sequentially; each tool returns page state. |
| Computer-Vision Selector | `browser/detector.py` | Accepts text “button text” or relative coordinates. |
| Dropdown Interaction | `browser_tools.dropdown.py` | Use options list, choose by value/text. |
| Wait / Retry | `browser_tools.wait.py` | Provide timeout & selector for dynamic pages. |

---

## 9. Advanced Tool Categories

| Category | Examples | Notes |
|----------|----------|-------|
| **OS / Dev** | `bash_tool`, `str_replace_tool` | Run shell cmds safely; shielded by permission gate. |
| **Multimodal** | `pdf_tool`, `audio_tool`, `image_gen_tool`, `video_gen_tool` | Use external APIs; store large outputs in workspace. |
| **Research** | `web_search_tool`, `deep_research_tool` | Combine search + visit + summarise flows. |
| **Memory** | `simple_memory`, `compactify_memory` | Persist knowledge across sessions. |
| **Visualization** | `visualizer`, `presentation_tool`, `slide_deck_tool` | Generate Markdown slides or HTML visualisations. |

---

## 10. Best Practices

1. **Keep Parameters Minimal** – fewer fields help the LLM call correctly.  
2. **Validate Inputs** – always sanity-check `params` before executing side-effects.  
3. **Be Idempotent** – repeated tool calls should not corrupt state.  
4. **Return Small Payloads** – large binaries ➜ save to file, return path.  
5. **Log Verbosely** – use `logging.getLogger(__name__)` to trace execution.  
6. **Unit-Test** – cover edge cases & error conditions.  
7. **Document** – add docstrings; update `docs/` when adding public tools.  
8. **Respect Security** – never read outside `workspace.root`; avoid dangerous shell commands.  
9. **Token Efficiency** – summarise long outputs before returning (use `token_counter`).  
10. **Versioning** – bump tool version or name if breaking schema changes.

---

## 11. Next Steps

* Explore source code under `src/ii_agent/tools/*` for real implementations.  
* Contribute a tool via PR—remember to update the registry and add tests.  
* Share feedback and ideas in GitHub Discussions!

Happy building 🛠️  
