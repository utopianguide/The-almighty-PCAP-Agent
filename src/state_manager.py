"""
State Manager - The Case File System
=====================================
Handles conversation history, context management, and persistent case storage.
Decouples storage (disk) from LLM context (RAM) for hot-swapping models.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
import tiktoken


@dataclass
class ToolExecution:
    """Record of a tool execution."""
    tool_name: str
    args: dict
    summary: str
    raw_output_path: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class ConversationTurn:
    """A single turn in the conversation."""
    id: int
    role: str  # "user" | "agent" | "system" | "tool"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    thought: Optional[str] = None
    tool_execution: Optional[ToolExecution] = None
    tokens: int = 0


@dataclass
class CaseFile:
    """The complete case file structure."""
    case_id: str
    pcap_file: str
    analyst: str = "Analyst"
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "active"  # "active" | "paused" | "completed"
    timeline: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    final_report: Optional[str] = None


class StateManager:
    """
    Manages the investigation state, conversation history, and case persistence.
    
    Features:
    - Persistent case file storage (JSON)
    - Token counting for context management
    - Smart context building with truncation
    - Hot-swap model support
    """
    
    def __init__(self, config: dict, pcap_file: str, case_id: Optional[str] = None):
        self.config = config
        self.pcap_file = pcap_file
        self.cases_dir = Path(config.get("output", {}).get("cases_directory", "./cases"))
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load case
        self.case_id = case_id or self._generate_case_id()
        self.case_path = self.cases_dir / f"{self.case_id}"
        self.case_path.mkdir(parents=True, exist_ok=True)
        
        self.logs_path = self.case_path / "logs"
        self.logs_path.mkdir(exist_ok=True)
        
        # Load or create case file
        self.case_file_path = self.case_path / "case.json"
        if self.case_file_path.exists():
            self.case = self._load_case()
        else:
            self.case = CaseFile(
                case_id=self.case_id,
                pcap_file=pcap_file
            )
            self._save_case()
        
        # Token counter (using tiktoken for estimation)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None
        
        # Current turn counter
        self.turn_counter = len(self.case.timeline)
        
        # Context tracking
        self.current_context_tokens = 0
        self._recalculate_tokens()
    
    def _generate_case_id(self) -> str:
        """Generate a unique case ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pcap_name = Path(self.pcap_file).stem[:20]
        return f"case_{pcap_name}_{timestamp}"
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Rough estimation if tokenizer unavailable
        return len(text) // 4
    
    def _recalculate_tokens(self):
        """Recalculate total context tokens."""
        total = 0
        for turn in self.case.timeline:
            if isinstance(turn, dict):
                total += turn.get("tokens", 0)
            else:
                total += turn.tokens
        self.current_context_tokens = total
    
    def _load_case(self) -> CaseFile:
        """Load case from disk."""
        with open(self.case_file_path, "r") as f:
            data = json.load(f)
        
        # Convert timeline dicts to dataclasses
        timeline = []
        for turn_data in data.get("timeline", []):
            if "tool_execution" in turn_data and turn_data["tool_execution"]:
                turn_data["tool_execution"] = ToolExecution(**turn_data["tool_execution"])
            timeline.append(ConversationTurn(**turn_data))
        
        data["timeline"] = timeline
        return CaseFile(**data)
    
    def _save_case(self):
        """Persist case to disk."""
        data = asdict(self.case)
        with open(self.case_file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def add_user_message(self, content: str) -> ConversationTurn:
        """Add a user message to the timeline."""
        self.turn_counter += 1
        tokens = self._count_tokens(content)
        
        turn = ConversationTurn(
            id=self.turn_counter,
            role="user",
            content=content,
            tokens=tokens
        )
        
        self.case.timeline.append(turn)
        self.current_context_tokens += tokens
        self._save_case()
        return turn
    
    def add_agent_response(
        self, 
        content: str, 
        thought: Optional[str] = None,
        tool_execution: Optional[ToolExecution] = None
    ) -> ConversationTurn:
        """Add an agent response to the timeline."""
        self.turn_counter += 1
        
        # Calculate tokens for all components
        tokens = self._count_tokens(content)
        if thought:
            tokens += self._count_tokens(thought)
        
        turn = ConversationTurn(
            id=self.turn_counter,
            role="agent",
            content=content,
            thought=thought,
            tool_execution=tool_execution,
            tokens=tokens
        )
        
        self.case.timeline.append(turn)
        self.current_context_tokens += tokens
        self._save_case()
        return turn
    
    def add_tool_output(
        self, 
        tool_name: str, 
        args: dict, 
        raw_output: str,
        summary: str,
        execution_time: float = 0.0
    ) -> tuple[ConversationTurn, str]:
        """
        Add tool execution result to timeline.
        Returns the turn and the path to raw output if saved.
        """
        self.turn_counter += 1
        
        # Save raw output to file
        raw_output_path = None
        if self.config.get("output", {}).get("save_raw_outputs", True):
            raw_output_path = self.logs_path / f"step_{self.turn_counter}_raw.txt"
            with open(raw_output_path, "w") as f:
                f.write(f"Tool: {tool_name}\n")
                f.write(f"Args: {json.dumps(args)}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n")
                f.write(raw_output)
        
        tool_exec = ToolExecution(
            tool_name=tool_name,
            args=args,
            summary=summary,
            raw_output_path=str(raw_output_path) if raw_output_path else None,
            execution_time=execution_time
        )
        
        tokens = self._count_tokens(summary)
        
        turn = ConversationTurn(
            id=self.turn_counter,
            role="tool",
            content=summary,
            tool_execution=tool_exec,
            tokens=tokens
        )
        
        self.case.timeline.append(turn)
        self.current_context_tokens += tokens
        self._save_case()
        
        return turn, str(raw_output_path) if raw_output_path else ""
    
    def add_finding(self, finding: str, severity: str = "info"):
        """Add an investigation finding."""
        self.case.findings.append({
            "id": len(self.case.findings) + 1,
            "finding": finding,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })
        self._save_case()
    
    def set_final_report(self, report: str):
        """Set the final investigation report."""
        self.case.final_report = report
        self.case.status = "completed"
        self._save_case()
    
    def get_context(self, model_config: dict) -> list[dict]:
        """
        Build context for LLM, respecting token limits.
        Returns list of messages for the LLM API.
        """
        max_tokens = model_config.get("context_window", 8000)
        safety_buffer = model_config.get("safety_buffer", 1000)
        available_tokens = max_tokens - safety_buffer
        
        messages = []
        used_tokens = 0
        
        # Always include system prompt (estimate ~500 tokens)
        system_tokens = 500
        used_tokens += system_tokens
        
        # Build messages from timeline (newest first for priority)
        for turn in reversed(self.case.timeline):
            turn_data = turn if isinstance(turn, ConversationTurn) else ConversationTurn(**turn)
            turn_tokens = turn_data.tokens or self._count_tokens(turn_data.content)
            
            if used_tokens + turn_tokens > available_tokens:
                # Add truncation notice
                messages.insert(0, {
                    "role": "system",
                    "content": "[Earlier conversation history truncated due to context limits]"
                })
                break
            
            msg = {"role": turn_data.role, "content": turn_data.content}
            
            # Add thought process for agent messages
            if turn_data.role == "agent" and turn_data.thought:
                msg["content"] = f"[Thought: {turn_data.thought}]\n{turn_data.content}"
            
            # Convert tool role to appropriate format
            if turn_data.role == "tool":
                msg["role"] = "assistant"
                tool_exec = turn_data.tool_execution
                if tool_exec:
                    if isinstance(tool_exec, dict):
                        msg["content"] = f"[Tool: {tool_exec.get('tool_name', 'unknown')}]\n{turn_data.content}"
                    else:
                        msg["content"] = f"[Tool: {tool_exec.tool_name}]\n{turn_data.content}"
            
            messages.insert(0, msg)
            used_tokens += turn_tokens
        
        self.current_context_tokens = used_tokens
        return messages
    
    def get_raw_log(self, step_id: int) -> Optional[str]:
        """Retrieve the full raw output for a specific step."""
        log_path = self.logs_path / f"step_{step_id}_raw.txt"
        if log_path.exists():
            with open(log_path, "r") as f:
                return f.read()
        return None
    
    def inject_full_log(self, step_id: int) -> bool:
        """
        Inject full raw log into context for detailed analysis.
        Used for Smart Context Expansion.
        """
        raw_log = self.get_raw_log(step_id)
        if raw_log:
            self.turn_counter += 1
            tokens = self._count_tokens(raw_log)
            
            turn = ConversationTurn(
                id=self.turn_counter,
                role="system",
                content=f"[Full log for step {step_id}]:\n{raw_log}",
                tokens=tokens
            )
            
            self.case.timeline.append(turn)
            self.current_context_tokens += tokens
            self._save_case()
            return True
        return False
    
    def get_context_usage(self, model_config: dict) -> dict:
        """Get current context usage statistics."""
        max_tokens = model_config.get("context_window", 8000)
        safety_buffer = model_config.get("safety_buffer", 1000)
        available = max_tokens - safety_buffer
        
        return {
            "used": self.current_context_tokens,
            "available": available,
            "max": max_tokens,
            "percentage": (self.current_context_tokens / available) * 100 if available > 0 else 0
        }
    
    def get_timeline_summary(self) -> list[dict]:
        """Get a summary of all timeline entries for display."""
        summary = []
        for turn in self.case.timeline:
            turn_data = turn if isinstance(turn, dict) else asdict(turn)
            summary.append({
                "id": turn_data["id"],
                "role": turn_data["role"],
                "preview": turn_data["content"][:100] + "..." if len(turn_data["content"]) > 100 else turn_data["content"],
                "timestamp": turn_data["timestamp"]
            })
        return summary
    
    def pause_case(self):
        """Pause the current investigation."""
        self.case.status = "paused"
        self._save_case()
    
    def resume_case(self):
        """Resume a paused investigation."""
        self.case.status = "active"
        self._save_case()
    
    @classmethod
    def list_cases(cls, cases_dir: str = "./cases") -> list[dict]:
        """List all available case files."""
        cases_path = Path(cases_dir)
        if not cases_path.exists():
            return []
        
        cases = []
        for case_dir in cases_path.iterdir():
            if case_dir.is_dir():
                case_file = case_dir / "case.json"
                if case_file.exists():
                    with open(case_file, "r") as f:
                        data = json.load(f)
                    cases.append({
                        "case_id": data.get("case_id"),
                        "pcap_file": data.get("pcap_file"),
                        "status": data.get("status"),
                        "start_time": data.get("start_time"),
                        "turns": len(data.get("timeline", []))
                    })
        
        return sorted(cases, key=lambda x: x["start_time"], reverse=True)


