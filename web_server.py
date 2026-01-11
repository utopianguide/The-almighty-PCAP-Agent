#!/usr/bin/env python3
"""
PCAP Forensic Analysis Agent - Web Server
==========================================
Flask-based web interface with ChatGPT-style conversational experience.
"""

import os
import json
import time
import queue
import threading
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
load_dotenv()

from src.state_manager import StateManager
from src.toolbox import Toolbox, TsharkNotFoundError
from src.llm_interface import LLMInterface
from src.utils import load_config, validate_pcap_file, OutputProcessor, format_duration


# =============================================================================
# Configuration
# =============================================================================

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pcap', 'pcapng', 'cap'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

# Global state for active sessions
active_sessions = {}


# =============================================================================
# Session Management
# =============================================================================

class WebForensicSession:
    """
    Manages a single forensic investigation session for the web.
    Implements ChatGPT-style tool usage with synthesized responses.
    """
    
    MAX_TOOL_ITERATIONS = 10  # Maximum tools to call before synthesizing
    
    def __init__(self, pcap_file: str, config: dict, case_id: Optional[str] = None, mode: str = "co-pilot"):
        self.config = config
        self.pcap_file = pcap_file
        self.mode = mode
        
        # Initialize components
        self.state = StateManager(config, pcap_file, case_id)
        self.toolbox = Toolbox(pcap_file, config)
        self.llm = LLMInterface(config)
        self.output_processor = OutputProcessor(config)
        
        # Session state
        self.iteration = 0
        self.max_iterations = config.get("agent", {}).get("max_iterations", 50)
        self.running = False
        self.mission_complete = False
        
        # Message queue for streaming to frontend
        self.message_queue = queue.Queue()
        
        # Current analysis state
        self.current_tool_results = []
        self.current_user_question = ""
        
    def get_session_info(self) -> dict:
        """Get current session information."""
        model_config = self.llm.model_config
        context_usage = self.state.get_context_usage(model_config)
        
        return {
            "case_id": self.state.case_id,
            "pcap_file": self.pcap_file,
            "mode": self.mode,
            "model": self.llm.get_model_info(),
            "status": self.state.case.status,
            "iteration": self.iteration,
            "context_usage": context_usage,
            "findings": self.state.case.findings,
            "timeline_count": len(self.state.case.timeline)
        }
    
    def push_event(self, event_type: str, data: dict):
        """Push an event to the message queue for SSE streaming."""
        self.message_queue.put({
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        })
    
    def process_message(self, user_message: str) -> None:
        """
        Process a user message using ChatGPT-style tool calling.
        
        Flow:
        1. Show thinking indicator
        2. Call tools as needed (in background)
        3. Synthesize results into a conversational response
        4. Send the final response
        """
        self.running = True
        self.current_user_question = user_message
        self.current_tool_results = []
        
        # Add user message to state
        self.state.add_user_message(user_message)
        self.push_event("user_message", {"content": user_message})
        
        # Start the agent loop
        self._run_chatgpt_style_loop()
    
    def start_autonomous(self) -> None:
        """Start autonomous analysis."""
        self.mode = "autonomous"
        initial_prompt = "Perform a comprehensive forensic analysis of this PCAP file. Identify any security incidents, suspicious activity, or anomalies. Provide a detailed report of your findings."
        self.process_message(initial_prompt)
    
    def _run_chatgpt_style_loop(self):
        """
        Run the ChatGPT-style agent loop.
        
        1. Ask LLM if it needs to call a tool
        2. If yes, call the tool and loop back
        3. If no, synthesize results and respond
        """
        self.push_event("thinking", {"status": "start"})
        
        tool_iterations = 0
        
        try:
            while tool_iterations < self.MAX_TOOL_ITERATIONS:
                tool_iterations += 1
                self.iteration += 1
                
                # Check iteration limit
                if self.iteration > self.max_iterations:
                    self.push_event("system", {
                        "message": f"Maximum iterations ({self.max_iterations}) reached.",
                        "style": "warning"
                    })
                    break
                
                # Build context for tool decision
                messages = self._build_tool_context()
                tools = self.toolbox.get_available_tools()
                
                # Ask LLM what tool to call (if any)
                response = self.llm.generate_tool_call(messages, tools)
                
                # Check if LLM is ready to respond (no more tools needed)
                if response.status == "ready" or not response.tool_name:
                    break
                
                # Execute the requested tool
                self._execute_tool_quietly(response.tool_name, response.tool_args or {})
            
            # Synthesize results into a conversational response
            self._synthesize_and_respond()
            
        except Exception as e:
            self.push_event("error", {"message": str(e)})
        finally:
            self.push_event("thinking", {"status": "end"})
    
    def _build_tool_context(self) -> list[dict]:
        """Build the message context for tool decisions."""
        messages = []
        
        # Add user question with explicit instruction
        if not self.current_tool_results:
            # First iteration - no tools called yet
            messages.append({
                "role": "user",
                "content": f"""User question: "{self.current_user_question}"

This is your FIRST response. You have NOT called any tools yet.
You MUST call a tool to get data from the PCAP file. Start with get_pcap_info or get_protocol_hierarchy.
Do NOT set ready_to_respond=true - you have no data yet."""
            })
        else:
            # We have tool results
            messages.append({
                "role": "user",
                "content": f"User question: {self.current_user_question}"
            })
            
            results_summary = "\n\nTool results you have gathered:\n"
            for result in self.current_tool_results:
                results_summary += f"\n### {result['tool_name']}:\n{result['result'][:1500]}\n"
            
            messages.append({
                "role": "assistant", 
                "content": results_summary
            })
            messages.append({
                "role": "user",
                "content": "Based on these results, do you need more data (call another tool), or do you have enough to answer the user's question (set ready_to_respond=true)?"
            })
        
        return messages
    
    def _execute_tool_quietly(self, tool_name: str, tool_args: dict):
        """
        Execute a tool and collect results without flooding the chat.
        Updates the 'searching' indicator with current activity.
        """
        # Update thinking indicator
        self.push_event("searching", {
            "message": f"Analyzing: {tool_name}..."
        })
        
        # Execute the tool
        start_time = time.time()
        result = self.toolbox.execute_tool(tool_name, tool_args)
        execution_time = time.time() - start_time
        
        if result.success:
            # Process output
            processed = self.output_processor.process(result.output)
            
            # Store result for synthesis
            self.current_tool_results.append({
                "tool_name": tool_name,
                "args": tool_args,
                "result": processed.full_text,
                "summary": processed.display_text[:200],
                "execution_time": execution_time
            })
            
            # Push tool result event (for collapsible sources)
            self.push_event("tool_result", {
                "tool_name": tool_name,
                "output": processed.display_text[:200],
                "truncated": processed.truncated,
                "total_lines": processed.total_lines,
                "execution_time": format_duration(execution_time)
            })
            
            # Record in state
            self.state.add_tool_output(
                tool_name=tool_name,
                args=tool_args,
                raw_output=processed.full_text,
                summary=processed.display_text,
                execution_time=execution_time
            )
        else:
            # Record error
            self.current_tool_results.append({
                "tool_name": tool_name,
                "args": tool_args,
                "result": f"Error: {result.error}",
                "summary": f"Error: {result.error}",
                "execution_time": execution_time
            })
    
    def _synthesize_and_respond(self):
        """
        Synthesize tool results into a conversational response.
        """
        if not self.current_tool_results:
            # No tools were called - just respond directly
            # This shouldn't happen often with our prompt, but handle it
            response_text = "I don't have enough information to answer that. Could you be more specific about what you'd like to know about the PCAP file?"
        else:
            # Check if this is a final report request
            is_final = "report" in self.current_user_question.lower() or \
                       "comprehensive" in self.current_user_question.lower() or \
                       self.mode == "autonomous"
            
            # Generate synthesized response
            response_text = self.llm.generate_synthesis(
                user_question=self.current_user_question,
                tool_results=self.current_tool_results,
                is_final_report=is_final
            )
        
        # Push the final response
        self.push_event("agent_analysis", {"content": response_text})
        
        # Record agent response
        self.state.add_agent_response(
            content=response_text,
            thought=f"Analyzed {len(self.current_tool_results)} data sources"
        )
        
        # Generate title if this is the first response and no title exists
        if not self.state.get_title() and self.iteration <= 3:
            self._generate_title(response_text)
        
        # Update context usage
        model_config = self.llm.model_config
        context_usage = self.state.get_context_usage(model_config)
        self.push_event("context_update", context_usage)
        
        # Check for high-confidence findings
        if self._contains_security_finding(response_text):
            self.state.add_finding(response_text[:500], "medium")
    
    def _generate_title(self, response_text: str):
        """Generate and save a title for the conversation."""
        try:
            title = self.llm.generate_title(
                user_question=self.current_user_question,
                response_summary=response_text[:500]
            )
            self.state.set_title(title)
            
            # Push title update to frontend
            self.push_event("title_update", {
                "case_id": self.state.case_id,
                "title": title
            })
        except Exception as e:
            # Title generation is non-critical, just log and continue
            print(f"Title generation failed: {e}")
    
    def _contains_security_finding(self, text: str) -> bool:
        """Check if text contains security-relevant findings."""
        keywords = [
            "attack", "malicious", "suspicious", "vulnerability", "exploit",
            "credential", "password", "exfiltrat", "breach", "unauthorized",
            "brute force", "injection", "scan", "reconnaissance"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)


# =============================================================================
# API Routes
# =============================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Serve the main application."""
    return send_from_directory('static', 'index.html')


@app.route('/api/upload', methods=['POST'])
def upload_pcap():
    """Upload a PCAP file and create a new session."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Allowed: pcap, pcapng, cap"}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Validate PCAP
    is_valid, error = validate_pcap_file(filepath)
    if not is_valid:
        os.remove(filepath)
        return jsonify({"error": error}), 400
    
    # Load config and create session
    try:
        config = load_config('config.yaml')
        mode = request.form.get('mode', 'co-pilot')
        
        session = WebForensicSession(filepath, config, mode=mode)
        session_id = session.state.case_id
        active_sessions[session_id] = session
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "session_info": session.get_session_info()
        })
    
    except TsharkNotFoundError as e:
        return jsonify({"error": f"Tshark not found: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/sessions/<session_id>/message', methods=['POST'])
def send_message(session_id):
    """Send a message to the agent."""
    if session_id not in active_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "No message provided"}), 400
    
    session = active_sessions[session_id]
    
    # Run in background thread
    thread = threading.Thread(
        target=session.process_message,
        args=(data['message'],)
    )
    thread.start()
    
    return jsonify({"success": True})


@app.route('/api/sessions/<session_id>/autonomous', methods=['POST'])
def start_autonomous(session_id):
    """Start autonomous analysis."""
    if session_id not in active_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session = active_sessions[session_id]
    
    # Run in background thread
    thread = threading.Thread(target=session.start_autonomous)
    thread.start()
    
    return jsonify({"success": True})


@app.route('/api/sessions/<session_id>/stream')
def stream_events(session_id):
    """Server-Sent Events stream for real-time updates."""
    if session_id not in active_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session = active_sessions[session_id]
    
    def generate():
        while True:
            try:
                # Wait for events with timeout
                event = session.message_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                # Send keepalive
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/sessions/<session_id>/info')
def get_session_info(session_id):
    """Get current session information."""
    if session_id not in active_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session = active_sessions[session_id]
    return jsonify(session.get_session_info())


@app.route('/api/sessions/<session_id>/findings')
def get_findings(session_id):
    """Get all findings for a session."""
    if session_id not in active_sessions:
        return jsonify({"error": "Session not found"}), 404
    
    session = active_sessions[session_id]
    return jsonify({"findings": session.state.case.findings})


@app.route('/api/cases')
def list_cases():
    """List all saved cases."""
    config = load_config('config.yaml')
    cases_dir = config.get("output", {}).get("cases_directory", "./cases")
    cases = StateManager.list_cases(cases_dir)
    return jsonify({"cases": cases})


@app.route('/api/cases/<case_id>/resume', methods=['POST'])
def resume_case(case_id):
    """Resume a previous case."""
    try:
        config = load_config('config.yaml')
        cases_dir = config.get("output", {}).get("cases_directory", "./cases")
        
        # Find the case
        cases = StateManager.list_cases(cases_dir)
        pcap_file = None
        for case in cases:
            if case['case_id'] == case_id:
                pcap_file = case['pcap_file']
                break
        
        if not pcap_file:
            return jsonify({"error": "Case not found"}), 404
        
        # Validate PCAP still exists
        is_valid, error = validate_pcap_file(pcap_file)
        if not is_valid:
            return jsonify({"error": f"PCAP file error: {error}"}), 400
        
        # Create session
        session = WebForensicSession(pcap_file, config, case_id=case_id)
        active_sessions[case_id] = session
        
        return jsonify({
            "success": True,
            "session_id": case_id,
            "session_info": session.get_session_info()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/models')
def list_models():
    """List available models."""
    config = load_config('config.yaml')
    models = list(config.get("models", {}).keys())
    current = config.get("current_model", "")
    return jsonify({"models": models, "current": current})


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  PCAP Forensic Analysis Agent - Web Interface")
    print("="*60)
    print("\n  Starting server at http://localhost:5000\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
