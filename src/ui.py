"""
Forensic UI - The Cyber-Analyst Interface
==========================================
Rich-based terminal UI with cyber/hacker aesthetic.
Features streaming responses, syntax highlighting, and context meters.
"""

import re
from typing import Optional, Callable
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.theme import Theme


# ═══════════════════════════════════════════════════════════════════════════════
# CYBER THEME DEFINITION
# ═══════════════════════════════════════════════════════════════════════════════

CYBER_THEME = Theme({
    # Core colors
    "cyber.primary": "bold #00ff9f",       # Neon green
    "cyber.secondary": "#00d4ff",           # Cyan
    "cyber.accent": "#ff006e",              # Magenta/Pink
    "cyber.warning": "#ffbe0b",             # Amber
    "cyber.error": "#ff0055",               # Red
    "cyber.muted": "#6b7280",               # Gray
    
    # Semantic colors
    "cyber.ip": "bold #00d4ff",             # IPs in cyan
    "cyber.port": "#fb5607",                # Ports in orange
    "cyber.protocol": "#8338ec",            # Protocols in purple
    "cyber.timestamp": "#6b7280",           # Timestamps in gray
    "cyber.success": "#00ff9f",             # Success green
    "cyber.danger": "#ff0055",              # Danger red
    
    # Role colors
    "cyber.user": "bold #00d4ff",           # User messages
    "cyber.agent": "bold #00ff9f",          # Agent messages
    "cyber.system": "#ffbe0b",              # System messages
    "cyber.tool": "#8338ec",                # Tool output
    
    # UI elements
    "cyber.border": "#00ff9f",
    "cyber.header": "bold #00ff9f on #1a1a2e",
    "cyber.dim": "dim #6b7280",
})


class ForensicUI:
    """
    Terminal UI for the PCAP Forensic Analysis Agent.
    
    Features:
    - Styled panels for different message types
    - Syntax highlighting for IPs, ports, protocols
    - Context usage meter
    - Streaming response support
    - Interactive prompts
    """
    
    # Regex patterns for syntax highlighting
    IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    PORT_PATTERN = re.compile(r'\b(?:port\s*)?(\d{1,5})\b', re.IGNORECASE)
    MAC_PATTERN = re.compile(r'\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b')
    TIMESTAMP_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}')
    
    def __init__(self, config: dict):
        self.config = config
        self.theme_name = config.get("ui", {}).get("theme", "cyber")
        self.show_context_meter = config.get("ui", {}).get("show_context_meter", True)
        self.syntax_highlighting = config.get("ui", {}).get("syntax_highlighting", True)
        
        # Initialize Rich console with theme
        self.console = Console(theme=CYBER_THEME, force_terminal=True)
        
        # Banner ASCII art
        self.banner = r'''
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ██████╗  ██████╗ █████╗ ██████╗     ███████╗ ██████╗ ██████╗ ███████╗███╗   ██╗██╗███████╗██╗ ██████╗███████╗ ║
║  ██╔══██╗██╔════╝██╔══██╗██╔══██╗    ██╔════╝██╔═══██╗██╔══██╗██╔════╝████╗  ██║██║██╔════╝██║██╔════╝██╔════╝ ║
║  ██████╔╝██║     ███████║██████╔╝    █████╗  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║█████╗  ██║██║     ███████╗ ║
║  ██╔═══╝ ██║     ██╔══██║██╔═══╝     ██╔══╝  ██║   ██║██╔══██║██╔══╝  ██║╚═██╗██║██║██╔══╝  ██║██║     ╚════██║ ║
║  ██║     ╚██████╗██║  ██║██║         ██║     ╚██████╔╝██║  ██║███████╗██║ ╚████║██║███████╗██║╚██████╗███████║ ║
║  ╚═╝      ╚═════╝╚═╝  ╚═╝╚═╝         ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝╚══════╝╚═╝ ╚═════╝╚══════╝ ║
║                            Autonomous PCAP Forensic Analysis Agent                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝'''
    
    def print_banner(self):
        """Display the startup banner."""
        # Simplified banner that fits better
        banner_text = """
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄    ▄▄▄▄▄▄▄ ▄▄▄▄▄▄▄ ▄▄▄▄▄▄   ▄▄▄▄▄▄▄ ▄▄    ▄ ┃
┃  █       █       █       █       █  █       █       █   ▄  █ █       █  █  █ █ ┃
┃  █    ▄  █       █   ▄   █    ▄  █  █    ▄▄▄█   ▄   █  █ █ █ █    ▄▄▄█   █▄█ █ ┃
┃  █   █▄█ █     ▄▄█  █▄█  █   █▄█ █  █   █▄▄▄█  █ █  █   █▄▄█▄█   █▄▄▄█       █ ┃
┃  █    ▄▄▄█    █  █       █    ▄▄▄█  █    ▄▄▄█  █▄█  █    ▄▄  █    ▄▄▄█  ▄    █ ┃
┃  █   █   █    █▄▄█   ▄   █   █      █   █   █       █   █  █ █   █▄▄▄█ █ █   █ ┃
┃  █▄▄▄█   █▄▄▄▄▄▄▄█▄▄█ █▄▄█▄▄▄█      █▄▄▄█   █▄▄▄▄▄▄▄█▄▄▄█  █▄█▄▄▄▄▄▄▄█▄█  █▄▄█ ┃
┃                                                                              ┃
┃              ⟨ Autonomous PCAP Forensic Analysis Agent ⟩                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"""
        self.console.print(Text(banner_text, style="cyber.primary"))
    
    def highlight_text(self, text: str) -> Text:
        """Apply syntax highlighting to text."""
        if not self.syntax_highlighting:
            return Text(text)
        
        result = Text(text)
        
        # Highlight IPs
        for match in self.IP_PATTERN.finditer(text):
            result.stylize("cyber.ip", match.start(), match.end())
        
        # Highlight timestamps
        for match in self.TIMESTAMP_PATTERN.finditer(text):
            result.stylize("cyber.timestamp", match.start(), match.end())
        
        # Highlight MACs
        for match in self.MAC_PATTERN.finditer(text):
            result.stylize("cyber.muted", match.start(), match.end())
        
        return result
    
    def print_session_info(self, pcap_file: str, case_id: str, model_info: dict):
        """Display session information panel."""
        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="cyber.muted")
        info_table.add_column(style="cyber.secondary")
        
        info_table.add_row("📁 PCAP File:", pcap_file)
        info_table.add_row("🔖 Case ID:", case_id)
        info_table.add_row("🤖 Model:", f"{model_info.get('name')} ({model_info.get('provider')})")
        info_table.add_row("📊 Context:", f"{model_info.get('context_window', 0):,} tokens")
        
        panel = Panel(
            info_table,
            title="[cyber.header]⟨ Session Info ⟩[/]",
            border_style="cyber.border",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def print_context_meter(self, usage: dict):
        """Display context usage meter."""
        if not self.show_context_meter:
            return
        
        used = usage.get("used", 0)
        available = usage.get("available", 1)
        percentage = usage.get("percentage", 0)
        
        # Determine color based on usage
        if percentage > 80:
            bar_style = "cyber.error"
            status = "⚠️ HIGH"
        elif percentage > 60:
            bar_style = "cyber.warning"
            status = "🔶 MEDIUM"
        else:
            bar_style = "cyber.success"
            status = "✅ OK"
        
        # Create progress bar
        filled = int(percentage / 2)  # 50 chars max
        bar = "█" * filled + "░" * (50 - filled)
        
        meter_text = Text()
        meter_text.append("Context: [", style="cyber.muted")
        meter_text.append(bar, style=bar_style)
        meter_text.append(f"] {percentage:.1f}% ", style="cyber.muted")
        meter_text.append(f"({used:,}/{available:,} tokens) ", style="cyber.muted")
        meter_text.append(status, style=bar_style)
        
        self.console.print(meter_text)
    
    def print_user_message(self, message: str):
        """Display a user message."""
        panel = Panel(
            self.highlight_text(message),
            title="[cyber.user]⟨ You ⟩[/]",
            border_style="cyber.secondary",
            padding=(0, 2)
        )
        self.console.print(panel)
    
    def print_agent_thought(self, thought: str):
        """Display agent's thought process."""
        text = Text()
        text.append("💭 ", style="cyber.muted")
        text.append(thought, style="italic cyber.muted")
        self.console.print(text)
    
    def print_agent_analysis(self, analysis: str):
        """Display agent's analysis/response."""
        panel = Panel(
            self.highlight_text(analysis),
            title="[cyber.agent]⟨ Agent Analysis ⟩[/]",
            border_style="cyber.primary",
            padding=(0, 2)
        )
        self.console.print(panel)
    
    def print_tool_execution(self, tool_name: str, command: str = None):
        """Display tool execution notice."""
        text = Text()
        text.append("⚡ Executing: ", style="cyber.tool")
        text.append(tool_name, style="bold cyber.tool")
        
        if command and self.config.get("agent", {}).get("show_commands", True):
            text.append("\n   └─ ", style="cyber.muted")
            text.append(command, style="dim")
        
        self.console.print(text)
    
    def print_tool_result(self, result: str, truncated: bool = False, total_lines: int = 0):
        """Display tool execution result."""
        content = self.highlight_text(result)
        
        title = "[cyber.tool]⟨ Tool Output ⟩[/]"
        if truncated:
            title = f"[cyber.tool]⟨ Tool Output ⟩[/] [cyber.warning]({total_lines} lines, truncated)[/]"
        
        panel = Panel(
            content,
            title=title,
            border_style="cyber.tool",
            padding=(0, 2)
        )
        self.console.print(panel)
    
    def print_system_message(self, message: str, style: str = "info"):
        """Display a system message."""
        styles = {
            "info": ("ℹ️", "cyber.secondary"),
            "warning": ("⚠️", "cyber.warning"),
            "error": ("❌", "cyber.error"),
            "success": ("✅", "cyber.success")
        }
        icon, color = styles.get(style, styles["info"])
        
        text = Text()
        text.append(f"{icon} ", style=color)
        text.append(message, style=color)
        self.console.print(text)
    
    def print_finding(self, finding: str, severity: str = "info"):
        """Display a finding."""
        severity_styles = {
            "critical": ("🚨", "cyber.error", "CRITICAL"),
            "high": ("🔴", "cyber.error", "HIGH"),
            "medium": ("🟠", "cyber.warning", "MEDIUM"),
            "low": ("🟡", "cyber.warning", "LOW"),
            "info": ("🔵", "cyber.secondary", "INFO")
        }
        icon, color, label = severity_styles.get(severity, severity_styles["info"])
        
        text = Text()
        text.append(f"{icon} [{label}] ", style=f"bold {color}")
        text.append(finding, style=color)
        self.console.print(text)
    
    def print_final_report(self, report: str):
        """Display the final investigation report."""
        panel = Panel(
            Markdown(report),
            title="[cyber.header]═══ FINAL INVESTIGATION REPORT ═══[/]",
            border_style="cyber.success",
            padding=(1, 2)
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()
    
    def print_plan(self, steps: list[str]):
        """Display the agent's plan."""
        text = Text()
        text.append("📋 Plan:\n", style="bold cyber.secondary")
        for i, step in enumerate(steps, 1):
            text.append(f"   {i}. {step}\n", style="cyber.muted")
        
        panel = Panel(
            text,
            border_style="cyber.muted",
            padding=(0, 1)
        )
        self.console.print(panel)
    
    def print_error(self, error: str):
        """Display an error message."""
        panel = Panel(
            Text(error, style="cyber.error"),
            title="[cyber.error]⟨ Error ⟩[/]",
            border_style="cyber.error",
            padding=(0, 2)
        )
        self.console.print(panel)
    
    def prompt_user(self, prompt: str = "Your input") -> str:
        """Get input from user."""
        return Prompt.ask(f"[cyber.user]{prompt}[/]")
    
    def prompt_confirm(self, message: str, default: bool = True) -> bool:
        """Get yes/no confirmation from user."""
        return Confirm.ask(f"[cyber.warning]{message}[/]", default=default)
    
    def prompt_approve_action(self, action: str, details: str = None) -> tuple[bool, Optional[str]]:
        """
        Prompt user to approve, reject, or modify an action.
        
        Returns:
            Tuple of (approved, user_input)
            - If approved: (True, None)
            - If rejected: (False, None)
            - If modified: (False, user_input)
        """
        self.console.print()
        text = Text()
        text.append("🔒 Proposed Action: ", style="cyber.warning")
        text.append(action, style="bold cyber.secondary")
        self.console.print(text)
        
        if details:
            self.console.print(Text(f"   └─ {details}", style="cyber.muted"))
        
        response = Prompt.ask(
            "[cyber.warning]Approve? (Y/n/edit)[/]",
            default="y"
        ).strip().lower()
        
        if response in ["y", "yes", ""]:
            return True, None
        elif response in ["n", "no"]:
            return False, None
        else:
            # User wants to provide alternative input
            return False, response
    
    def print_spinner(self, message: str) -> Progress:
        """Create and return a spinner for long operations."""
        return Progress(
            SpinnerColumn(style="cyber.primary"),
            TextColumn("[cyber.muted]{task.description}"),
            console=self.console,
            transient=True
        )
    
    def stream_agent_response(self, token_generator, on_complete: Callable = None):
        """
        Stream agent response tokens to the console.
        
        Args:
            token_generator: Generator yielding (token, final_response) tuples
            on_complete: Callback when streaming completes
        """
        text_buffer = ""
        
        with Live(
            Panel(Text("▌", style="cyber.primary blink"), border_style="cyber.primary"),
            console=self.console,
            refresh_per_second=10,
            transient=True
        ) as live:
            for token, response in token_generator:
                if response is not None:
                    # Final response
                    if on_complete:
                        on_complete(response)
                    break
                
                text_buffer += token
                display_text = Text(text_buffer + "▌", style="cyber.primary")
                live.update(Panel(
                    display_text,
                    title="[cyber.agent]⟨ Agent ⟩[/]",
                    border_style="cyber.primary"
                ))
    
    def print_help(self):
        """Display help information."""
        help_text = """
[bold cyber.primary]Available Commands:[/]

  [cyber.secondary]/help[/]        - Show this help message
  [cyber.secondary]/status[/]      - Show current investigation status
  [cyber.secondary]/findings[/]    - List all findings so far
  [cyber.secondary]/recall N[/]    - Load full output from step N
  [cyber.secondary]/model NAME[/]  - Switch to a different model
  [cyber.secondary]/save[/]        - Save current session
  [cyber.secondary]/quit[/]        - End investigation

[bold cyber.primary]Investigation Tips:[/]

  • Start with high-level questions: "What's in this capture?"
  • Ask specific follow-ups: "Show me traffic to suspicious IPs"
  • Request deep dives: "Follow the TCP stream between X and Y"
  • Guide the analysis: "Check for SQL injection patterns"
"""
        panel = Panel(
            Markdown(help_text),
            title="[cyber.header]⟨ Help ⟩[/]",
            border_style="cyber.secondary",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def print_status(self, case_info: dict, findings: list, context_usage: dict):
        """Display current investigation status."""
        # Case info
        status_table = Table.grid(padding=(0, 2))
        status_table.add_column(style="cyber.muted")
        status_table.add_column(style="cyber.secondary")
        
        status_table.add_row("Case ID:", case_info.get("case_id", "N/A"))
        status_table.add_row("PCAP:", case_info.get("pcap_file", "N/A"))
        status_table.add_row("Status:", case_info.get("status", "N/A"))
        status_table.add_row("Steps:", str(case_info.get("turns", 0)))
        
        panel = Panel(
            status_table,
            title="[cyber.header]⟨ Investigation Status ⟩[/]",
            border_style="cyber.primary",
            padding=(1, 2)
        )
        self.console.print(panel)
        
        # Context usage
        self.print_context_meter(context_usage)
        
        # Findings summary
        if findings:
            self.console.print()
            self.console.print(Text(f"📋 {len(findings)} finding(s) recorded", style="cyber.secondary"))
    
    def clear_screen(self):
        """Clear the console."""
        self.console.clear()
    
    def print_separator(self):
        """Print a visual separator."""
        self.console.print(Text("─" * 80, style="cyber.muted"))

