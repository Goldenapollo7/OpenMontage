# OpenMontage + Open WebUI

Run OpenMontage from an Open WebUI chat window instead of a terminal-based coding agent.

Open WebUI is a chat interface, so it needs help in two places before it can drive a
video production:

| What a normal harness gives the model | How Open WebUI gets it |
|---|---|
| Read/write files in the project | `om_read_file`, `om_write_file`, `om_list_files` from the tool below |
| Run `python`, `npm`, `ffmpeg` | `om_run_command` (a real shell, in the project folder) |
| Know which providers exist | `om_preflight` (runs the registry preflight from `AGENT_GUIDE.md`) |
| The production rules | The **system prompt** below, which points the model at `AGENT_GUIDE.md` |

> **The trap to avoid:** Open WebUI's built-in code execution (Pyodide) runs Python in
> your *browser*. It cannot see `C:\OpenMontage`, cannot `pip install`, and cannot run
> npm or FFmpeg. Without the tool below, the model can only write you instructions
> instead of making a video.

---

## 1. Where the Open WebUI backend runs matters

The tool executes commands **in the Open WebUI backend process**, so the backend must be
on the machine that has the OpenMontage clone and its toolchain (Python + Node + FFmpeg).

| Setup | Does it work? | Notes |
|---|---|---|
| `pip install open-webui` on Windows, then `open-webui serve` | ✅ Recommended | Same machine as your clone and Python; no mounting, no container toolchain. |
| Open WebUI in Docker, project folder bind-mounted | ⚠️ Works with setup | The container needs its own Python deps, Node, and FFmpeg, and renders read/write through the mount. Fine if you prefer containers; slower to set up. |
| Open WebUI in Docker, no mount | ❌ | The container cannot see your Windows project. |
| Open WebUI on a server, project on your laptop | ❌ | Different machines. |

Install (Windows, one command per line):

```powershell
pip install open-webui
open-webui serve
```

Then open <http://localhost:8080>, create the first account (it becomes admin), and
connect a model under **Settings → Connections** (your OpenAI/Anthropic/Google API key,
or a local Ollama instance).

**Use a strong tool-calling model.** The repo's workflow is long (read guide → preflight
→ propose → script → scenes → assets → compose → render), so a frontier API model works
best; small local models tend to stop calling tools halfway. In **Admin Settings →
Models**, keep tool calling on **Native (Agentic)** mode — Legacy mode cannot use these
tools reliably.

---

## 2. Add the tool

1. Download [`openmontage_tool.py`](openmontage_tool.py) (or copy its contents).
2. In Open WebUI: **Workspace → Tools → ➕ New Tool**.
3. Paste the whole file, give it the id/name `openmontage`, and **Save**.
4. Open the tool's **Valves** and set:
   - `project_root` → `C:\OpenMontage` (wherever you cloned the repo)
   - `timeout_seconds` → `900` if you render long videos
   - `confirm_commands` → `true` if other people can use this instance
5. **Workspace → Models → ➕ New Model**, and set:
   - **Base model:** your strong tool-calling model
   - **Tools:** enable `openmontage`
   - **System prompt:** paste the block from section 4

Then open a chat with that model.

---

## 3. Verify the wiring before you trust it

Send this as your first message:

```text
Run om_status, then om_preflight, and show me the results.
```

You should get the project path, a `Checkout: complete` line, toolchain versions, and the
provider menu summary (composition runtimes, configured/total per capability, and the
one-key setup offers).

- `project_root` is wrong if `om_status` reports a missing project folder.
- `om_preflight` failing means the repo's Python dependencies are missing — in the clone
  run `python scripts/setup.py`, or `python -m pip install -r requirements.txt` at a
  minimum. Open WebUI's backend Python is tried first, then `python` / `python3` on PATH.
- If the menu shows a `runtime_warnings` entry like
  `tools.video.green_screen_composite: module not loaded (numpy)`, a tool is present but
  could not import — install the dependency rather than assuming the feature is gone.

---

## 4. System prompt (paste into the model)

```text
You are the production orchestrator for OpenMontage, an agentic video production
system whose checkout lives in the project folder you have tools for.

Ground rules:
1. Before any production work, read AGENT_GUIDE.md with om_read_file, then
   PROJECT_CONTEXT.md. Do not improvise the workflow.
2. All production goes through a pipeline: pick one from pipeline_defs/*.yaml, read
   the manifest, then read the matching stage skill in skills/pipelines/<pipeline>/
   before each stage. Never write ad-hoc scripts that bypass the pipeline.
3. Before proposing a plan, run om_preflight and show the user what is available now
   and what one API key would unlock. Then propose: pipeline, providers, stage list,
   estimated cost, and what the output will look like. Get approval before spending
   money or generating assets.
4. Use om_run_command for every shell action. One command per call — never chain with
   && or || (parse error in Windows PowerShell 5.1). Commands run in the project
   folder already.
5. Read each tool's Layer 3 skill before calling it (the tool's agent_skills field
   names the file under .agents/skills/).
6. Report progress honestly: name substitutions, degraded paths, and failures. Never
   claim a render exists without checking the file with ffprobe or om_list_files.
7. When a render finishes, tell the user the output path and offer to preview it in
   Remotion Studio (npm start inside remotion-composer).
```

---

## 5. First prompt

```text
Make a 60-second animated explainer about how neural networks learn.
```

Without API keys, expect the zero-key path: Piper narration, Remotion motion graphics,
free archival footage where a pipeline needs it. With stock keys (Pexels, Pixabay,
Unsplash) or image/video providers in `.env`, the agent can reach for those instead —
it should show you the difference during preflight.

### Watching the output

- Renders land under `projects\<project-slug>\` in your clone (visible in File Explorer).
- To preview Remotion compositions in a browser:

  ```powershell
  cd C:\OpenMontage\remotion-composer
  npm start
  ```

  Then open <http://localhost:3000>. This is the visual UI for the React composition
  layer — it renders single compositions, it does not run the pipeline.

---

## 6. Security

This tool runs shell commands with the privileges of the process running Open WebUI —
that is the point, but it deserves care:

- Keep the Open WebUI instance local (or behind auth you trust).
- Do not give the Workspace/Tools area to untrusted users; a Workspace Tool is arbitrary
  Python on your machine.
- `confirm_commands = true` makes the model ask before each command.
- The tool refuses a small set of catastrophic patterns and blocks file paths outside
  the project folder, but that is a guardrail, not a sandbox. A containerized backend
  (option 2 in section 1) is the real isolation boundary.

---

## 7. Alternatives inside Open WebUI

- **Open Terminal** (Open WebUI's own shell-enabled execution backend) gives the model a
  container with shell, files, and previews. Use it if you prefer container isolation —
  mount your clone into that container and install Python deps, Node, and FFmpeg there,
  otherwise the pipeline cannot run.
- **MCP (streamable HTTP) or mcpo** — expose a filesystem/shell MCP server as Open WebUI
  tools if you would rather not run in-process Python. MCP registration is admin-only and
  the setup is longer than dropping in this tool.
- **Docker + this tool** — mount the clone (`-v C:\OpenMontage:/workspace/OpenMontage`),
  set `project_root` to `/workspace/OpenMontage`, and install the toolchain in the image.
