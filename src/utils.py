"""
Utilities - Helper Functions
=============================
Configuration loading, output processing, and other utilities.
"""

import yaml
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file
    
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        # Return default config if file doesn't exist
        return get_default_config()
    
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    return config


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "current_model": "gpt4o",
        "models": {
            "gpt4o": {
                "name": "gpt-4o",
                "provider": "openai",
                "context_window": 128000,
                "safety_buffer": 4000,
                "max_output_tokens": 4096
            }
        },
        "agent": {
            "mode": "co-pilot",
            "max_iterations": 50,
            "auto_approve_safe_ops": True,
            "show_commands": True
        },
        "output": {
            "truncate_threshold": 100,
            "truncate_preview_lines": 50,
            "save_raw_outputs": True,
            "cases_directory": "./cases"
        },
        "tshark": {
            "path": "",
            "timeout": 120,
            "max_packets": 0
        },
        "ui": {
            "theme": "cyber",
            "show_context_meter": True,
            "syntax_highlighting": True,
            "spinner_speed": 80
        }
    }


def save_config(config: dict, config_path: str = "config.yaml"):
    """Save configuration to YAML file."""
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


@dataclass
class ProcessedOutput:
    """Result of output processing."""
    display_text: str
    full_text: str
    truncated: bool
    total_lines: int
    preview_lines: int


class OutputProcessor:
    """
    Handles processing and truncation of tool outputs.
    """
    
    def __init__(self, config: dict):
        self.threshold = config.get("output", {}).get("truncate_threshold", 100)
        self.preview_lines = config.get("output", {}).get("truncate_preview_lines", 50)
    
    def process(self, output: str) -> ProcessedOutput:
        """
        Process tool output for display.
        
        Args:
            output: Raw output from tool
        
        Returns:
            ProcessedOutput with display text and metadata
        """
        lines = output.split("\n")
        total_lines = len(lines)
        
        if total_lines <= self.threshold:
            return ProcessedOutput(
                display_text=output,
                full_text=output,
                truncated=False,
                total_lines=total_lines,
                preview_lines=total_lines
            )
        
        # Truncate output
        preview = lines[:self.preview_lines]
        display_text = "\n".join(preview)
        display_text += f"\n\n[... {total_lines - self.preview_lines} more lines truncated ...]"
        display_text += "\n[SYSTEM: If you need the full output for analysis, request full context.]"
        
        return ProcessedOutput(
            display_text=display_text,
            full_text=output,
            truncated=True,
            total_lines=total_lines,
            preview_lines=self.preview_lines
        )
    
    def summarize_large_output(self, output: str, max_chars: int = 500) -> str:
        """
        Create a brief summary of large output for context.
        
        Args:
            output: Full output text
            max_chars: Maximum characters for summary
        
        Returns:
            Summarized text
        """
        lines = output.split("\n")
        total_lines = len(lines)
        
        if len(output) <= max_chars:
            return output
        
        # Get first and last few lines
        head_lines = lines[:5]
        tail_lines = lines[-3:] if total_lines > 8 else []
        
        summary = "\n".join(head_lines)
        summary += f"\n[... {total_lines - 8} lines omitted ...]"
        if tail_lines:
            summary += "\n" + "\n".join(tail_lines)
        
        return summary[:max_chars]


def validate_pcap_file(file_path: str) -> tuple[bool, str]:
    """
    Validate that a file exists and appears to be a PCAP file.
    
    Args:
        file_path: Path to the file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(file_path)
    
    if not path.exists():
        return False, f"File not found: {file_path}"
    
    if not path.is_file():
        return False, f"Not a file: {file_path}"
    
    # Check extension
    valid_extensions = {".pcap", ".pcapng", ".cap", ".dmp"}
    if path.suffix.lower() not in valid_extensions:
        return False, f"Invalid file extension. Expected: {valid_extensions}"
    
    # Check file is readable and not empty
    try:
        size = path.stat().st_size
        if size == 0:
            return False, "File is empty"
    except OSError as e:
        return False, f"Cannot read file: {e}"
    
    return True, ""


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def parse_command(user_input: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse user input for commands.
    
    Commands start with / (e.g., /help, /recall 5)
    
    Args:
        user_input: Raw user input
    
    Returns:
        Tuple of (command, argument) or (None, None) if not a command
    """
    user_input = user_input.strip()
    
    if not user_input.startswith("/"):
        return None, None
    
    parts = user_input[1:].split(maxsplit=1)
    command = parts[0].lower() if parts else None
    argument = parts[1] if len(parts) > 1 else None
    
    return command, argument


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use as a filename."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    
    # Limit length
    return name[:100]


class Colors:
    """ANSI color codes for fallback terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    
    @classmethod
    def colorize(cls, text: str, *styles) -> str:
        """Apply color styles to text."""
        style_codes = "".join(styles)
        return f"{style_codes}{text}{cls.RESET}"


