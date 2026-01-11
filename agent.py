#!/usr/bin/env python3
"""
PCAP Forensic Analysis Agent
=============================
Autonomous AI-powered post-incident forensic analysis of network captures.

Usage:
    python agent.py --pcap <file.pcap>
    python agent.py --pcap <file.pcap> --mode autonomous
    python agent.py --resume <case_id>
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from src.state_manager import StateManager
from src.toolbox import Toolbox, TsharkNotFoundError
from src.llm_interface import LLMInterface, LLMResponse
from src.ui import ForensicUI
from src.utils import (
    load_config, 
    validate_pcap_file, 
    parse_command,
    OutputProcessor,
    format_duration
)


class ForensicAgent:
    """
    The main agent orchestrator.
    
    Coordinates the analysis loop between:
    - StateManager (memory/context)
    - Toolbox (tshark operations)
    - LLMInterface (brain)
    - ForensicUI (interface)
    """
    
    def __init__(
        self, 
        pcap_file: str, 
        config: dict, 
        case_id: Optional[str] = None,
        mode: str = "co-pilot"
    ):
        self.config = config
        self.pcap_file = pcap_file
        self.mode = mode
        
        # Initialize components
        self.ui = ForensicUI(config)
        self.state = StateManager(config, pcap_file, case_id)
        self.toolbox = Toolbox(pcap_file, config)
        self.llm = LLMInterface(config)
        self.output_processor = OutputProcessor(config)
        
        # Agent state
        self.iteration = 0
        self.max_iterations = config.get("agent", {}).get("max_iterations", 50)
        self.running = False
        self.mission_complete = False
    
    def run(self):
        """Main agent loop."""
        self.running = True
        self.ui.clear_screen()
        self.ui.print_banner()
        self.ui.print_separator()
        
        # Display session info
        self.ui.print_session_info(
            self.pcap_file,
            self.state.case_id,
            self.llm.get_model_info()
        )
        self.ui.print_separator()
        
        # Initial context
        self.ui.print_system_message(
            f"Investigation started. Mode: {self.mode}",
            style="success"
        )
        self.ui.print_system_message(
            "Type /help for available commands, or ask a question to begin.",
            style="info"
        )
        
        try:
            self._main_loop()
        except KeyboardInterrupt:
            self.ui.print_system_message("\nInvestigation paused.", style="warning")
            self.state.pause_case()
        finally:
            self.running = False
    
    def _main_loop(self):
        """The core agent loop."""
        # Get initial user input or start autonomous analysis
        if self.mode == "autonomous":
            initial_prompt = "Begin comprehensive forensic analysis of this PCAP file. Start with a high-level overview and systematically investigate any anomalies."
            self.state.add_user_message(initial_prompt)
            self.ui.print_user_message(initial_prompt)
        
        while self.running and not self.mission_complete:
            self.iteration += 1
            
            # Check iteration limit
            if self.iteration > self.max_iterations:
                self.ui.print_system_message(
                    f"Maximum iterations ({self.max_iterations}) reached. Concluding investigation.",
                    style="warning"
                )
                break
            
            # In co-pilot mode, always get user input first (except first iteration in autonomous)
            if self.mode == "co-pilot" or (self.mode == "autonomous" and self.iteration > 1 and not self._has_pending_action()):
                user_input = self._get_user_input()
                if user_input is None:  # User quit
                    break
                if user_input == "":  # Empty input, continue
                    continue
            
            # Update context meter
            model_config = self.llm.model_config
            context_usage = self.state.get_context_usage(model_config)
            self.ui.print_context_meter(context_usage)
            
            # Generate agent response
            self.ui.print_system_message("Analyzing...", style="info")
            
            messages = self.state.get_context(model_config)
            tools = self.toolbox.get_available_tools()
            
            start_time = time.time()
            response = self.llm.generate(messages, tools)
            generation_time = time.time() - start_time
            
            # Handle parse errors
            if response.parse_error:
                self.ui.print_error(f"Response parse error: {response.parse_error}")
                self.ui.print_system_message("Raw response:", style="warning")
                self.ui.print_agent_analysis(response.raw_content[:500])
                continue
            
            # Display thought process
            if response.thought:
                self.ui.print_agent_thought(response.thought)
            
            # Display analysis
            if response.analysis:
                self.ui.print_agent_analysis(response.analysis)
            
            # Handle Smart Context Request
            if response.request_full_context and response.context_step_id:
                if self._handle_context_request(response.context_step_id):
                    continue  # Re-run loop with new context
            
            # Execute tool if requested
            if response.tool_name:
                tool_approved = self._handle_tool_execution(
                    response.tool_name,
                    response.tool_args or {}
                )
                if not tool_approved:
                    # User rejected or modified - handled in the function
                    continue
            
            # Record agent response
            self.state.add_agent_response(
                content=response.analysis or response.raw_content,
                thought=response.thought
            )
            
            # Check for completion
            if response.status == "finished":
                self.mission_complete = True
                if response.final_report:
                    self.ui.print_final_report(response.final_report)
                    self.state.set_final_report(response.final_report)
                
                self.ui.print_system_message(
                    f"Investigation completed in {self.iteration} steps.",
                    style="success"
                )
                break
            
            # Handle findings
            if response.confidence > 0.7 and response.analysis:
                # Auto-record high-confidence findings
                self.state.add_finding(response.analysis, "medium")
            
            self.ui.print_separator()
    
    def _get_user_input(self) -> Optional[str]:
        """Get and process user input."""
        self.ui.console.print()
        user_input = self.ui.prompt_user("You")
        
        # Check for commands
        command, arg = parse_command(user_input)
        
        if command:
            return self._handle_command(command, arg)
        
        if user_input.strip():
            self.state.add_user_message(user_input)
            self.ui.print_user_message(user_input)
        
        return user_input
    
    def _handle_command(self, command: str, arg: Optional[str]) -> Optional[str]:
        """Handle slash commands."""
        if command == "help":
            self.ui.print_help()
            return ""
        
        elif command == "quit" or command == "exit":
            self.ui.print_system_message("Ending investigation...", style="warning")
            self.state.pause_case()
            return None
        
        elif command == "status":
            case_info = {
                "case_id": self.state.case.case_id,
                "pcap_file": self.state.case.pcap_file,
                "status": self.state.case.status,
                "turns": len(self.state.case.timeline)
            }
            context_usage = self.state.get_context_usage(self.llm.model_config)
            self.ui.print_status(case_info, self.state.case.findings, context_usage)
            return ""
        
        elif command == "findings":
            if self.state.case.findings:
                for finding in self.state.case.findings:
                    self.ui.print_finding(
                        finding.get("finding", ""),
                        finding.get("severity", "info")
                    )
            else:
                self.ui.print_system_message("No findings recorded yet.", style="info")
            return ""
        
        elif command == "recall":
            if arg:
                try:
                    step_id = int(arg)
                    if self.state.inject_full_log(step_id):
                        self.ui.print_system_message(
                            f"Full log from step {step_id} loaded into context.",
                            style="success"
                        )
                    else:
                        self.ui.print_system_message(
                            f"No raw log found for step {step_id}.",
                            style="warning"
                        )
                except ValueError:
                    self.ui.print_error("Invalid step ID. Usage: /recall <step_number>")
            else:
                self.ui.print_error("Usage: /recall <step_number>")
            return ""
        
        elif command == "model":
            if arg:
                try:
                    self.llm.switch_model(arg)
                    self.ui.print_system_message(
                        f"Switched to model: {arg}",
                        style="success"
                    )
                    self.ui.print_session_info(
                        self.pcap_file,
                        self.state.case_id,
                        self.llm.get_model_info()
                    )
                except ValueError as e:
                    self.ui.print_error(str(e))
            else:
                models = list(self.config.get("models", {}).keys())
                self.ui.print_system_message(
                    f"Available models: {', '.join(models)}",
                    style="info"
                )
            return ""
        
        elif command == "save":
            self.state._save_case()
            self.ui.print_system_message(
                f"Session saved to: {self.state.case_path}",
                style="success"
            )
            return ""
        
        else:
            self.ui.print_error(f"Unknown command: /{command}")
            return ""
    
    def _handle_tool_execution(self, tool_name: str, tool_args: dict) -> bool:
        """
        Handle tool execution with approval flow.
        
        Returns True if tool was executed, False if rejected/modified.
        """
        # Format the action for display
        args_str = ", ".join(f"{k}={v}" for k, v in tool_args.items())
        action_desc = f"{tool_name}({args_str})" if args_str else f"{tool_name}()"
        
        # Check if we need approval
        safe_tools = [
            "get_pcap_info", "get_protocol_hierarchy", "get_ip_conversations",
            "get_tcp_conversations", "get_udp_conversations", "get_endpoints",
            "get_http_requests", "get_http_responses", "get_dns_queries",
            "get_dns_responses", "get_expert_info", "get_io_stats"
        ]
        
        auto_approve = self.config.get("agent", {}).get("auto_approve_safe_ops", True)
        needs_approval = not (auto_approve and tool_name in safe_tools)
        
        if needs_approval and self.mode == "co-pilot":
            approved, user_input = self.ui.prompt_approve_action(action_desc)
            
            if not approved:
                if user_input:
                    # User provided alternative input
                    self.state.add_user_message(user_input)
                    self.ui.print_user_message(user_input)
                else:
                    self.ui.print_system_message("Action rejected.", style="warning")
                return False
        
        # Execute the tool
        self.ui.print_tool_execution(tool_name, action_desc)
        
        start_time = time.time()
        result = self.toolbox.execute_tool(tool_name, tool_args)
        execution_time = time.time() - start_time
        
        if not result.success:
            self.ui.print_error(f"Tool error: {result.error}")
            return False
        
        # Process output
        processed = self.output_processor.process(result.output)
        
        # Display result
        self.ui.print_tool_result(
            processed.display_text,
            truncated=processed.truncated,
            total_lines=processed.total_lines
        )
        
        # Record in state
        self.state.add_tool_output(
            tool_name=tool_name,
            args=tool_args,
            raw_output=processed.full_text,
            summary=processed.display_text,
            execution_time=execution_time
        )
        
        self.ui.print_system_message(
            f"Executed in {format_duration(execution_time)}",
            style="info"
        )
        
        return True
    
    def _handle_context_request(self, step_id: int) -> bool:
        """
        Handle agent request for full context from a previous step.
        
        Returns True if context was loaded.
        """
        self.ui.print_system_message(
            f"Agent requests full context from step {step_id}",
            style="warning"
        )
        
        if self.mode == "co-pilot":
            approved = self.ui.prompt_confirm(
                f"Load full log from step {step_id}? This will use additional context tokens."
            )
            if not approved:
                return False
        
        if self.state.inject_full_log(step_id):
            self.ui.print_system_message(
                f"Full context loaded from step {step_id}",
                style="success"
            )
            return True
        else:
            self.ui.print_system_message(
                f"No raw log found for step {step_id}",
                style="warning"
            )
            return False
    
    def _has_pending_action(self) -> bool:
        """Check if there's a pending action from the agent."""
        # In autonomous mode, check if the last turn was from the agent
        if not self.state.case.timeline:
            return False
        
        last_turn = self.state.case.timeline[-1]
        if hasattr(last_turn, 'role'):
            return last_turn.role == "agent"
        return last_turn.get("role") == "agent"


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="PCAP Forensic Analysis Agent - AI-powered network forensics"
    )
    parser.add_argument(
        "--pcap", "-p",
        type=str,
        help="Path to PCAP file to analyze"
    )
    parser.add_argument(
        "--resume", "-r",
        type=str,
        help="Resume a previous case by case ID"
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["autonomous", "co-pilot", "manual"],
        default="co-pilot",
        help="Agent interaction mode (default: co-pilot)"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List available cases to resume"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Handle list-cases
    if args.list_cases:
        cases = StateManager.list_cases(
            config.get("output", {}).get("cases_directory", "./cases")
        )
        if cases:
            print("\nAvailable cases:")
            print("-" * 60)
            for case in cases:
                print(f"  {case['case_id']}")
                print(f"    PCAP: {case['pcap_file']}")
                print(f"    Status: {case['status']}, Steps: {case['turns']}")
                print()
        else:
            print("No cases found.")
        return
    
    # Validate arguments
    if not args.pcap and not args.resume:
        parser.error("Either --pcap or --resume is required")
    
    # Determine PCAP file and case ID
    pcap_file = args.pcap
    case_id = args.resume
    
    if args.resume and not args.pcap:
        # Try to find PCAP from case file
        cases = StateManager.list_cases(
            config.get("output", {}).get("cases_directory", "./cases")
        )
        for case in cases:
            if case["case_id"] == args.resume:
                pcap_file = case["pcap_file"]
                break
        
        if not pcap_file:
            print(f"Error: Case '{args.resume}' not found.")
            sys.exit(1)
    
    # Validate PCAP file
    is_valid, error = validate_pcap_file(pcap_file)
    if not is_valid:
        print(f"Error: {error}")
        sys.exit(1)
    
    # Check for tshark
    try:
        toolbox = Toolbox(pcap_file, config)
    except TsharkNotFoundError as e:
        print(f"Error: {e}")
        print("\nPlease install Wireshark/Tshark:")
        print("  Windows: https://www.wireshark.org/download.html")
        print("  Linux: sudo apt install tshark")
        print("  macOS: brew install wireshark")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Run the agent
    try:
        agent = ForensicAgent(
            pcap_file=pcap_file,
            config=config,
            case_id=case_id,
            mode=args.mode
        )
        agent.run()
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


