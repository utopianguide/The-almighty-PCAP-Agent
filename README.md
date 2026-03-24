<div align="center">

# 🔬 PCAP Forensic Analysis Agent

**Drop a `.pcap`. Ask a question. Get a full security investigation.**

*An autonomous AI agent that thinks like a senior SOC analyst — powered by GPT-4o, Claude, or your own local LLM.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-orange?style=for-the-badge)](https://anthropic.com)
[![Flask](https://img.shields.io/badge/Flask-Web_UI-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)

</div>

---

## 🧠 What Is This?

Network forensics is slow, manual, and requires deep expertise. You open Wireshark, stare at 50,000 packets, and hope you notice the right anomaly.

**This agent does that for you — autonomously.**

Hand it a PCAP file. It will systematically investigate using real Tshark commands, reason about what it finds, follow suspicious threads, and deliver a structured incident report — all in natural language.

> *"Tell me what happened in this capture."*  
> Ten seconds later: *"FTP brute force detected. 5,000+ failed logins from 192.168.1.105. Successful auth at 10:47. 500MB exfiltrated to external IP."*

---

## ✨ Why This Is Different

Most "AI + security" demos slap an LLM on top of a static dataset. This agent **actually runs forensic tools in real time**:

| Feature | This Agent |
|---------|-----------|
| 🔎 **Real Tshark Analysis** | 20+ live forensic tools — not hardcoded outputs |
| 🤖 **Autonomous Investigation** | Agent decides what to query next, follows anomalies |
| 🌐 **Dual Interface** | Beautiful Web UI *and* a rich terminal CLI |
| 🔄 **Hot-swap LLMs** | Switch between GPT-4o, Claude, or local vLLM mid-session |
| 💾 **Persistent Cases** | Save, pause, and resume any investigation |
| 🧩 **Human-in-the-Loop** | Approve, reject, or redirect agent actions in co-pilot mode |
| ⚡ **SSE Streaming** | Real-time tool execution updates in the browser |
| 🔒 **No Shell Injection** | All Tshark commands are fully parameterized |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Interfaces                           │
│   ┌──────────────────┐    ┌──────────────────────────┐  │
│   │  CLI (agent.py)  │    │ Web UI (web_server.py)   │  │
│   │  Rich terminal   │    │ Flask + SSE streaming    │  │
│   └────────┬─────────┘    └─────────┬────────────────┘  │
└────────────┼──────────────────────┼───────────────────┘
             │                      │
             ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│                   ForensicAgent Core                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ LLMInterface │  │ StateManager │  │   Toolbox     │  │
│  │ (Brain)      │  │ (Memory)     │  │ (20+ Tools)   │  │
│  │ GPT-4o       │  │ Case files   │  │ Tshark wraps  │  │
│  │ Claude       │  │ Timeline     │  │               │  │
│  │ vLLM         │  │ Findings     │  │               │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- **Wireshark/Tshark** installed and in PATH
- API key for OpenAI or Anthropic (or a local vLLM server)

```bash
# Install Tshark
# Windows: https://www.wireshark.org/download.html
sudo apt install tshark       # Ubuntu/Debian
brew install wireshark         # macOS
```

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/NoFund_AI_Cursor_Opus
cd NoFund_AI_Cursor_Opus

python -m venv venv
source venv/bin/activate       # Windows: .\venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your API key(s)
```

### Launch (Web UI — Recommended)

```bash
python web_server.py
# Open http://localhost:5000
```

### Launch (Terminal CLI)

```bash
# Co-pilot mode — you guide, agent assists
python agent.py --pcap capture.pcap

# Autonomous mode — fully automatic investigation
python agent.py --pcap capture.pcap --mode autonomous

# Resume a previous investigation
python agent.py --resume case_capture_20231027_100000

# List all saved cases
python agent.py --list-cases
```

---

## 🌐 Web Interface

The web interface gives you a **ChatGPT-style experience** for PCAP analysis:

- 📤 Drag-and-drop file upload
- 💬 Conversational Q&A about your capture
- 🔍 Live "searching..." indicators as tools execute
- 📋 Collapsible tool output sources
- 🚀 One-click autonomous analysis
- 📂 Case history and resume functionality

```bash
python web_server.py
# → http://localhost:5000
```

---

## 🛠️ Forensic Tool Arsenal

The agent has access to **20+ specialized forensic tools** wrapping Tshark:

### 📊 Overview
| Tool | Description |
|------|-------------|
| `get_pcap_info` | File statistics — packets, duration, size |
| `get_protocol_hierarchy` | Full protocol distribution breakdown |
| `get_io_stats` | Traffic volume over time |

### 🤝 Conversations
| Tool | Description |
|------|-------------|
| `get_ip_conversations` | All IP-to-IP communication pairs |
| `get_tcp_conversations` | TCP connections with port info |
| `get_udp_conversations` | UDP communications |

### 🌐 Protocol Analysis
| Tool | Description |
|------|-------------|
| `get_http_requests/responses` | Full web traffic |
| `get_dns_queries/responses` | DNS lookups and answers |
| `get_ftp_commands/responses` | FTP operations |
| `get_smtp_traffic` | Email traffic |
| `get_tls_handshakes` | SSL/TLS connections |

### 🚨 Detection
| Tool | Description |
|------|-------------|
| `detect_port_scan` | Port scanning / reconnaissance |
| `get_credentials` | Cleartext credential exposure |
| `get_suspicious_ports` | Non-standard port traffic |
| `get_expert_info` | Wireshark expert warnings |

### 🔬 Deep Analysis
| Tool | Description |
|------|-------------|
| `filter_packets` | Custom Wireshark display filters |
| `follow_stream` | Reconstruct TCP/UDP sessions |
| `extract_fields` | Extract specific packet fields |
| `search_payload` | Search packet contents |

---

## 💬 CLI Commands

When running in CLI mode, you can use slash commands at any time:

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/status` | Investigation status + context usage |
| `/findings` | All recorded security findings |
| `/recall N` | Reload full output from step N into context |
| `/model NAME` | Hot-swap to a different LLM |
| `/save` | Persist current session to disk |
| `/quit` | Save and exit |

---

## ⚙️ Configuration

Everything is in `config.yaml`:

```yaml
# Which model to use by default
current_model: "claude_sonnet"   # claude_sonnet | gpt4o | local_llama

models:
  gpt4o:
    provider: openai
    name: gpt-4o
    context_window: 128000
  claude_sonnet:
    provider: anthropic
    name: claude-sonnet-4-20250514
    context_window: 200000
  local_llama:
    provider: vllm_api
    api_base: http://localhost:8000/v1
    name: meta-llama-3-70b-instruct

agent:
  mode: "co-pilot"              # co-pilot | autonomous
  max_iterations: 50
  auto_approve_safe_ops: true

output:
  truncate_threshold: 100       # Lines before output is summarized
  save_raw_outputs: true
  cases_directory: "./cases"

ui:
  theme: "cyber"
  show_context_meter: true
  syntax_highlighting: true
```

---

## 📁 Project Structure

```
NoFund_AI_Cursor_Opus/
│
├── agent.py              # CLI entry point — ForensicAgent orchestrator
├── web_server.py         # Flask web server + SSE streaming
├── config.yaml           # All configuration
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
│
├── src/
│   ├── llm_interface.py  # Multi-provider LLM abstraction (OpenAI/Anthropic/vLLM)
│   ├── toolbox.py        # 20+ Tshark wrapper functions
│   ├── state_manager.py  # Case persistence, timeline, context management
│   ├── ui.py             # Rich cyber-themed terminal interface
│   └── utils.py          # Config loading, output processing, helpers
│
├── static/               # Web UI (HTML/CSS/JS)
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
│
└── cases/                # Saved investigations (git-ignored)
    └── case_*/
        ├── case.json     # Case metadata, timeline, findings
        └── logs/         # Raw tool outputs for context recall
```

---

## 🔒 Security Design

This project was built with security first:

- **No shell injection** — all Tshark commands use argument arrays, never `shell=True`
- **Filter validation** — display filters are validated before execution  
- **Local processing** — your PCAP data never leaves your machine
- **Parameterized commands** — all inputs are sanitized before passing to Tshark
- **Key isolation** — API keys live in `.env`, never in code or version control

---

## 📊 Example Session Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃            PCAP FORENSICS — Autonomous Analysis Agent              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📁 PCAP File:  incident_capture.pcap
🔖 Case ID:    case_incident_20231027_100000  
🤖 Model:      claude-sonnet-4-20250514 (anthropic)

💭 Analyzing protocol distribution...
→ [get_protocol_hierarchy] 90% TCP · 85% FTP · 5% HTTP

💭 Unusual FTP volume detected. Checking login history...
→ [get_ftp_commands] 5,000+ failed AUTH attempts from 192.168.1.105

🔴 [HIGH] Brute force confirmed. Checking post-auth activity...
→ [follow_stream] Found STOR confidential_db_dump.zip (500MB)

═════════════════ FINAL REPORT ═════════════════

Attack Type:   FTP Brute Force → Data Exfiltration
Attacker IP:   192.168.1.105
Victim IP:     10.0.0.5
Timeline:      Brute force at 10:15 · Success at 10:47 · Exfil complete at 11:23
Impact:        confidential_db_dump.zip (500MB) transferred to external IP
IOCs:          192.168.1.105, 10.0.0.5, FTP port 21
```

---

## 📦 Dependencies

```
flask / flask-cors         → Web server
anthropic / openai         → LLM providers
rich                       → Terminal UI
python-dotenv              → Environment management
pyyaml                     → Config parsing
httpx                      → Local vLLM HTTP client
werkzeug                   → File upload security
```

---

## 🤝 Contributing

Pull requests are welcome. Ideas for extension:

- [ ] Export findings to STIX/TAXII format
- [ ] Threat intelligence feed integration (VirusTotal, AbuseIPDB)
- [ ] Additional protocol parsers (Modbus, DNP3 for ICS/SCADA)
- [ ] Docker containerization
- [ ] Timeline visualization in web UI

---

## 📝 License

MIT — use it, fork it, build on it.

---

<div align="center">

*Built as a graduation project — Post-Incident Forensic Analysis using Autonomous LLM Agents*

**[Wireshark/Tshark](https://www.wireshark.org/) · [Rich](https://github.com/Textualize/rich) · [OpenAI](https://openai.com) · [Anthropic](https://anthropic.com)**

</div>
