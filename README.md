# 🧠 SentientOS

> **Autonomous AI Operating Environment — Final-Year Project Prototype**

A polished, dark-themed dashboard that demonstrates a secure, rule-based autonomous task system. Runs locally on Ubuntu WSL and displays in any browser on Windows.

---

## Features

| Feature | Detail |
|---|---|
| 🖥️ Dashboard | Live system stats, recent tasks, activity feed |
| ⌨️ Command Centre | Natural-language input → rule-based task planner |
| 🔒 Security Gateway | Every file action validated before execution |
| 🔐 Human Approval | State-changing ops require explicit click-to-approve |
| 📋 Task Timeline | Step-by-step visual plan with status badges |
| 📜 Activity Log | Filterable log of all actions and outcomes |
| 🗄️ SQLite History | Persistent task and activity records |
| 📁 Workspace Sandbox | Files isolated to `./workspace/` only |

---

## Requirements

- **Ubuntu WSL** (Windows Subsystem for Linux) or native Ubuntu
- **Python 3.10+**
- **pip**

---

## Setup (one-time)

Open a **WSL terminal** and run:

```bash
# Navigate to the project
cd ~/SentientOS

# (Recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

```bash
# Quick launch using the helper script:
bash run.sh

# Or directly with Python:
python3 -m streamlit run app.py
```

Streamlit will print a **Local URL** — open it in your Windows browser:

```
  Local URL: http://localhost:8501
```


---

## Try These Demo Commands

Type any of these into the **Command Centre** tab:

| Command | What it does |
|---|---|
| `list workspace files` | Lists all files in ./workspace |
| `read notes.txt` | Reads the sample notes file |
| `read readme.md` | Reads the sample README |
| `create file hello.txt with content 'Hello!'` | Creates a file (requires approval) |
| `show system status` | Displays platform/Python info |
| `show security policy` | Shows all active security rules |
| `help` | Shows command reference |

> Sidebar also has **clickable demo buttons** for all commands above.

---

## Running Tests

```bash
# Run tests with the test script:
bash test.sh

# Or directly with pytest:
python3 -m pytest tests/ -v
```

Tests cover:
- ✅ Permitted file reads and writes
- 🚫 Blocked absolute paths
- 🚫 Blocked path traversal (`../../`)
- 🚫 Blocked shell extensions (`.sh`, `.py`, `.exe`)
- 🚫 Oversized content rejection
- 🚫 Unsafe filename characters
- ✅ Planner command parsing
- ✅ Security policy assertions

---

## Project Structure

```
SentientOS/
├── app.py                  # Streamlit dashboard (entry point)
├── requirements.txt
├── README.md
├── sentientos/             # Core package
│   ├── __init__.py
│   ├── database.py         # SQLite activity log
│   ├── security.py         # Security gateway (path validation)
│   ├── tools.py            # Restricted workspace file tools
│   ├── planner.py          # Rule-based NL command planner
│   └── executor.py         # Step executor with approval gating
├── tests/
│   ├── __init__.py
│   ├── test_security.py    # Security & tools tests
│   └── test_planner.py     # Planner parsing tests
└── workspace/              # Sandboxed file area (read/write allowed here only)
    ├── notes.txt
    ├── readme.md
    └── sample_data.csv
```

---

## Security Design

```
User Command
     │
     ▼
 Planner (rule-based regex)
     │  creates TaskPlan with steps
     ▼
 Executor (step runner)
     │  each step calls security.validate_*()
     ▼
 Security Gateway (independent Python module)
     │  checks path, extension, size, traversal
     ▼
 Tool (list / read / create)
     │  only executes if all checks pass
     ▼
 SQLite Activity Log
```

**What is NEVER allowed:**
- Shell command execution (`os.system`, `subprocess`, `eval`)
- Network requests
- Absolute paths or `../` traversal
- Non-text file extensions
- Files > 64 KB
- Any state change without human approval

---

## No API Key Required

SentientOS is fully offline. The planner is rule-based (regex matching) — there is no LLM, no OpenAI, no Gemini, no network calls of any kind.

---

## License

MIT — built as a final-year project prototype.
