# 🔬 PCAP Forensic Analysis Agent

> **Autonomous AI-powered Post-Incident Forensic Analysis of Network Captures**

An intelligent agent that analyzes PCAP files to identify security incidents, using LLM-powered reasoning combined with Tshark analysis tools.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)

---

## 🎯 Overview

This agent acts as a **Junior Security Analyst** that you can hand a PCAP file and say "Tell me what happened." It will:

1. **Systematically analyze** the network capture using Tshark
2. **Identify anomalies** and suspicious patterns
3. **Investigate** potential threats autonomously
4. **Generate** a comprehensive incident report

### Key Features

- 🤖 **Autonomous Investigation** - Agent decides what to analyze next
- 🧠 **Smart Context Management** - Handles large outputs with intelligent summarization
- 💾 **Persistent Case Files** - Save and resume investigations
- 🔄 **Hot-swap Models** - Switch between GPT-4, Claude, or local LLMs
- 🎨 **Cyber-themed UI** - Beautiful terminal interface with Rich
- 👤 **Human-in-the-Loop** - Approve, reject, or modify agent actions

---

## 📋 Prerequisites

- **Python 3.10+**
- **Wireshark/Tshark** installed and in PATH
- **API Key** for OpenAI or Anthropic (or local LLM setup)

### Install Tshark

```bash
# Windows: Download from https://www.wireshark.org/download.html

# Linux (Debian/Ubuntu)
sudo apt install tshark

# macOS
brew install wireshark
```

---

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
cd NoFund_AI_Cursor_Opus

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
# OPENAI_API_KEY=sk-...
# or
# ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run the Agent

```bash
# Basic usage (co-pilot mode)
python agent.py --pcap capture.pcap

# Autonomous mode (fully automatic)
python agent.py --pcap capture.pcap --mode autonomous

# Resume a previous investigation
python agent.py --resume case_capture_20231027_100000

# List saved cases
python agent.py --list-cases
```

---

## 🎮 Usage Modes

### Co-Pilot Mode (Default)
You guide the investigation, agent assists with analysis.
```bash
python agent.py --pcap file.pcap --mode co-pilot
```

### Autonomous Mode
Agent conducts full investigation independently.
```bash
python agent.py --pcap file.pcap --mode autonomous
```

---

## 💬 Interactive Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help information |
| `/status` | Display investigation status |
| `/findings` | List all recorded findings |
| `/recall N` | Load full output from step N |
| `/model NAME` | Switch to different model |
| `/save` | Save current session |
| `/quit` | End investigation |

---

## 🛠️ Available Analysis Tools

The agent has access to these forensic tools:

### Overview Tools
- `get_pcap_info` - File statistics (size, packets, duration)
- `get_protocol_hierarchy` - Protocol distribution
- `get_io_stats` - Traffic volume over time

### Conversation Analysis
- `get_ip_conversations` - IP-to-IP communications
- `get_tcp_conversations` - TCP connections with ports
- `get_udp_conversations` - UDP communications

### Protocol Analysis
- `get_http_requests` / `get_http_responses` - Web traffic
- `get_dns_queries` / `get_dns_responses` - DNS lookups
- `get_ftp_commands` / `get_ftp_responses` - FTP operations
- `get_smtp_traffic` - Email traffic
- `get_tls_handshakes` - SSL/TLS connections

### Detection Tools
- `get_suspicious_ports` - Non-standard port traffic
- `get_credentials` - Cleartext credentials
- `detect_port_scan` - Port scanning activity
- `get_expert_info` - Wireshark warnings

### Custom Analysis
- `filter_packets` - Custom Wireshark display filters
- `extract_fields` - Extract specific packet fields
- `follow_stream` - Reconstruct TCP/UDP sessions
- `search_payload` - Search packet contents

---

## 📁 Project Structure

```
├── agent.py              # Main entry point
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
│
├── src/
│   ├── __init__.py
│   ├── state_manager.py  # Case file & context management
│   ├── toolbox.py        # Tshark wrapper functions
│   ├── llm_interface.py  # LLM provider abstraction
│   ├── ui.py             # Rich terminal interface
│   └── utils.py          # Helper utilities
│
└── cases/                # Saved investigations
    └── case_*/
        ├── case.json     # Case metadata & timeline
        └── logs/         # Raw tool outputs
```

---

## ⚙️ Configuration

Edit `config.yaml` to customize:

```yaml
# Model selection
current_model: "claude_sonnet"  # or "gpt4o", "local_llama"

# Agent behavior
agent:
  mode: "co-pilot"              # autonomous | co-pilot | manual
  max_iterations: 50
  auto_approve_safe_ops: true

# Output processing
output:
  truncate_threshold: 100       # Lines before truncation
  save_raw_outputs: true
  cases_directory: "./cases"

# UI preferences
ui:
  theme: "cyber"
  show_context_meter: true
  syntax_highlighting: true
```

---

## 📊 Example Session

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃          PCAP FORENSICS - Autonomous Analysis Agent              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

📁 PCAP File: incident_capture.pcap
🔖 Case ID: case_incident_20231027_100000
🤖 Model: claude-sonnet-4-20250514 (anthropic)

> [Agent]: Analyzing protocol distribution...
> [Tool]: get_protocol_hierarchy()

⟨ Tool Output ⟩
Protocol hierarchy: 90% TCP, 85% FTP, 5% HTTP

> [Agent]: High FTP traffic detected. Investigating...

💭 "Unusual volume of FTP suggests possible data exfiltration"

> [Agent]: Found 500MB transfer from 192.168.1.105 to 10.0.0.5
> [Agent]: Checking for brute force indicators...

🔴 [HIGH] 5000+ failed FTP login attempts detected

═══ FINAL INVESTIGATION REPORT ═══

**Attack Type**: FTP Brute Force + Data Exfiltration
**Attacker IP**: 192.168.1.105
**Victim IP**: 10.0.0.5
**Impact**: confidential_db_dump.zip (500MB) exfiltrated
**Timeline**: Brute force at 10:15, successful login at 10:47
```

---

## 🔒 Security Considerations

- **Input Sanitization**: All Tshark commands are parameterized
- **Filter Validation**: Display filters are validated before execution
- **No Shell Injection**: Commands never use shell=True
- **Local Processing**: Your PCAP data stays on your machine
- **API Keys**: Never committed, stored in .env

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- [ ] Additional detection signatures
- [ ] More protocol parsers
- [ ] Web UI option
- [ ] Export to STIX/TAXII
- [ ] Integration with threat intel feeds

---

## 📝 License

MIT License - See LICENSE file

---

## 🙏 Acknowledgments

- [Wireshark/Tshark](https://www.wireshark.org/) - Network analysis
- [Rich](https://github.com/Textualize/rich) - Terminal UI
- [OpenAI](https://openai.com/) / [Anthropic](https://anthropic.com/) - LLM APIs

---

*Built for graduation project - Post-incident Forensic Analysis using Autonomous Agents*

