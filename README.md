<div align="center">

# EchoTrace

**Autonomous PCAP Forensic Analysis Framework**

*Next-generation network security investigation powered by Large Language Models.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)
[![Architecture: LLM-Driven](https://img.shields.io/badge/Architecture-Autonomous_Agent-412991?style=for-the-badge)](#architecture)

</div>

---

## Overview

EchoTrace is an enterprise-grade autonomous forensic agent designed for rapid post-incident network analysis. Built to operate as an automated Security Operations Center (SOC) analyst, EchoTrace ingests raw PCAP files, intelligently queries network traffic using native Tshark tools, and synthesizes findings into structured incident reports.

Unlike static, rule-based detection engines, EchoTrace utilizes dynamic reasoning to follow suspicious communication threads, identify complex anomalies, and autonomously pivot its investigation based on real-time findings.

---

## Technical Capabilities

EchoTrace interfaces directly with Tshark to perform deterministic technical analysis, combining the reliability of established network tooling with the deductive reasoning of foundational AI models. 

### Core Features
- **Dynamic Tool Execution**: Equipped with over 20 discrete forensic functions ranging from broad protocol hierarchy analysis to deep payload extraction.
- **LLM Agnostic**: Seamlessly hot-swappable between OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), and local deployments (vLLM) to meet compliance and data privacy requirements.
- **State Persistence**: Complex investigations are persisted as case files, allowing security analysts to pause, resume, and audit the agent's decision tree.
- **Dual Interfaces**: Deployable as a high-throughput CLI tool or a collaborative web interface featuring Server-Sent Events (SSE) for real-time investigation streaming.
- **Secure Execution Context**: Designed with zero shell-injection risk. All filtering and command execution vectors are strictly parameterized.

---

## System Architecture

```text
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
│  │ Abstraction  │  │ Case logs    │  │ Tshark wraps  │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Installation & Deployment

### Prerequisites

- Python 3.10 or higher
- **Wireshark/Tshark** installed and present in the system PATH
- Appropriate API credentials or a reachable local LLM endpoint

### Setup

```bash
git clone https://github.com/utopianguide/NoFund_AI_Cursor_Opus
cd EchoTrace

python -m venv venv
source venv/bin/activate       # Windows: .\venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Configure applicable API keys within .env
```

---

## Usage

### Web Interface Deployment

The web console provides a collaborative, chat-driven environment for PCAP analysis, featuring real-time execution logs and collapsible data sources.

```bash
python web_server.py
# Access the dashboard at http://localhost:5000
```

### Command Line Interface

The CLI offers a low-overhead interface suitable for integration into existing incident response workflows.

```bash
# Co-pilot mode (Analyst directs, agent executes)
python agent.py --pcap capture.pcap

# Autonomous mode (Agent handles full investigation lifecycle)
python agent.py --pcap capture.pcap --mode autonomous

# Resume a persisted case
python agent.py --resume case_capture_20231027_100000
```

---

## Tool Arsenal Reference

EchoTrace wraps Tshark functionality into discrete tools the LLM can invoke. 

| Category | Available Tools |
|----------|----------------|
| **Metadata** | `get_pcap_info`, `get_protocol_hierarchy`, `get_io_stats` |
| **Topology** | `get_ip_conversations`, `get_tcp_conversations`, `get_udp_conversations` |
| **Application** | `get_http_requests`, `get_dns_queries`, `get_ftp_commands`, `get_smtp_traffic`, `get_tls_handshakes` |
| **Heuristics** | `detect_port_scan`, `get_credentials`, `get_suspicious_ports`, `get_expert_info` |
| **Deep Inspection** | `filter_packets`, `follow_stream`, `extract_fields`, `search_payload` |

---

## Configuration Management

Behavioral tuning and model parameters are managed via `config.yaml`:

```yaml
current_model: "claude_sonnet"   # Supported: claude_sonnet, gpt4o, local_llama

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
  mode: "co-pilot"
  max_iterations: 50
  auto_approve_safe_ops: true
```

---

## License

This software is released under the [MIT License](LICENSE). 

See documentation for details regarding third-party service agreements associated with LLM providers utilized within this framework.
