"""
LLM Interface - The Brain Connector
====================================
Generic interface for different LLM providers.
Supports OpenAI, Anthropic, and local vLLM APIs.
"""

import os
import json
import re
from typing import Optional, Generator
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Structured response from LLM."""
    raw_content: str
    thought: Optional[str] = None
    analysis: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    request_full_context: bool = False
    context_step_id: Optional[int] = None
    status: str = "continue"  # "continue" | "finished" | "need_input"
    final_report: Optional[str] = None
    confidence: float = 0.8
    parse_error: Optional[str] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(self, messages: list[dict], system_prompt: str) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    def stream(self, messages: list[dict], system_prompt: str) -> Generator[str, None, None]:
        """Stream response tokens from the LLM."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, config: dict):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        self.config = config
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = config.get("name", "gpt-4o")
        self.max_tokens = config.get("max_output_tokens", 4096)
        self.temperature = config.get("temperature")  # None means use API default
    
    def generate(self, messages: list[dict], system_prompt: str) -> str:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        kwargs = {
            "model": self.model,
            "messages": full_messages,
            "max_completion_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        
        response = self.client.chat.completions.create(**kwargs)
        
        return response.choices[0].message.content
    
    def stream(self, messages: list[dict], system_prompt: str) -> Generator[str, None, None]:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        kwargs = {
            "model": self.model,
            "messages": full_messages,
            "max_completion_tokens": self.max_tokens,
            "stream": True,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        
        stream = self.client.chat.completions.create(**kwargs)
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicProvider(BaseLLMProvider):
    """Anthropic API provider."""
    
    def __init__(self, config: dict):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.config = config
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.model = config.get("name", "claude-sonnet-4-20250514")
        self.max_tokens = config.get("max_output_tokens", 4096)
    
    def generate(self, messages: list[dict], system_prompt: str) -> str:
        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "assistant"
            anthropic_messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        # Ensure messages alternate (Anthropic requirement)
        anthropic_messages = self._ensure_alternating(anthropic_messages)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=anthropic_messages
        )
        
        return response.content[0].text
    
    def stream(self, messages: list[dict], system_prompt: str) -> Generator[str, None, None]:
        anthropic_messages = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "system"] else "assistant"
            anthropic_messages.append({
                "role": role,
                "content": msg["content"]
            })
        
        anthropic_messages = self._ensure_alternating(anthropic_messages)
        
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=anthropic_messages
        ) as stream:
            for text in stream.text_stream:
                yield text
    
    def _ensure_alternating(self, messages: list[dict]) -> list[dict]:
        """Ensure messages alternate between user and assistant."""
        if not messages:
            return [{"role": "user", "content": "Begin analysis."}]
        
        result = []
        prev_role = None
        
        for msg in messages:
            if msg["role"] == prev_role:
                # Merge with previous message
                result[-1]["content"] += "\n\n" + msg["content"]
            else:
                result.append(msg)
                prev_role = msg["role"]
        
        # Ensure starts with user
        if result and result[0]["role"] != "user":
            result.insert(0, {"role": "user", "content": "Begin analysis."})
        
        # Ensure ends with user (for continuing conversation)
        if result and result[-1]["role"] != "user":
            result.append({"role": "user", "content": "Continue."})
        
        return result


class VLLMProvider(BaseLLMProvider):
    """Local vLLM API provider."""
    
    def __init__(self, config: dict):
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx package not installed. Run: pip install httpx")
        
        self.config = config
        self.api_base = config.get("api_base", "http://localhost:8000/v1")
        self.model = config.get("name", "meta-llama-3-70b-instruct")
        self.max_tokens = config.get("max_output_tokens", 2048)
        self.client = httpx.Client(timeout=120.0)
    
    def generate(self, messages: list[dict], system_prompt: str) -> str:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.client.post(
            f"{self.api_base}/chat/completions",
            json={
                "model": self.model,
                "messages": full_messages,
                "max_tokens": self.max_tokens,
                "temperature": 0.3
            }
        )
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    def stream(self, messages: list[dict], system_prompt: str) -> Generator[str, None, None]:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        with self.client.stream(
            "POST",
            f"{self.api_base}/chat/completions",
            json={
                "model": self.model,
                "messages": full_messages,
                "max_tokens": self.max_tokens,
                "temperature": 0.3,
                "stream": True
            }
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


class LLMInterface:
    """
    Main interface for interacting with LLMs.
    Handles provider selection, response parsing, and structured output.
    """
    
    # System prompt for tool-calling mode (internal agent loop)
    TOOL_CALL_PROMPT = '''You are an expert Cyber Security Forensic Analyst investigating a PCAP network capture file.

AVAILABLE TOOLS:
{tools}

CRITICAL RULES:
1. You MUST call tools to get data. You have NO prior knowledge of this PCAP file.
2. If this is your FIRST response, you MUST call a tool (start with get_pcap_info or get_protocol_hierarchy).
3. NEVER set ready_to_respond=true unless you have ACTUAL tool results to reference.
4. If you haven't called any tools yet, you are NOT ready to respond.

RESPONSE FORMAT - Always respond with ONLY valid JSON (no other text):
{{
    "thought": "Brief reasoning",
    "tool_name": "tool_to_call",
    "tool_args": {{}},
    "ready_to_respond": false
}}

When you have gathered enough data from tools:
{{
    "thought": "I have analyzed the data and can now answer",
    "tool_name": null,
    "tool_args": null,
    "ready_to_respond": true
}}

FIRST RESPONSE STRATEGY:
- General questions → call get_pcap_info AND get_protocol_hierarchy
- Questions about IPs/hosts → call get_ip_conversations
- Questions about HTTP → call get_http_requests
- Questions about credentials → call get_credentials or get_ftp_commands
- Questions about attacks → call get_expert_info and get_suspicious_ports'''

    # System prompt for synthesis mode (generating the final user-facing response)
    SYNTHESIS_PROMPT = '''You are a friendly, expert Cyber Security Forensic Analyst. Based on your analysis of the PCAP data, provide a clear, helpful response to the user.

CONTEXT - Here is what you discovered from your analysis:
{tool_results}

USER'S QUESTION:
{user_question}

INSTRUCTIONS:
- Respond naturally in markdown format - this will be rendered in a chat interface
- Be conversational but professional
- Highlight key findings with **bold** or bullet points
- If you found security issues, clearly explain the severity
- Use technical terms but explain them when helpful
- Include relevant IPs, ports, and protocols when discussing findings
- If data was exfiltrated or credentials were exposed, make that very clear
- End with a follow-up question or suggestion when appropriate

Remember: You're having a conversation, not writing a formal report. Be helpful and direct.'''

    # System prompt for generating conversation titles
    TITLE_PROMPT = '''Generate a very short title (3-6 words max) for this PCAP analysis conversation.
The title should capture the main topic or finding.

User's question: {user_question}
Agent's response summary: {response_summary}

Respond with ONLY the title text, nothing else. Examples:
- "FTP Credential Breach Analysis"
- "HTTP Traffic Investigation"
- "DNS Tunneling Detection"
- "Suspicious Port Scan Review"'''

    # System prompt for final report generation
    REPORT_PROMPT = '''You are a Cyber Security Forensic Analyst. Generate a comprehensive investigation report based on your analysis.

ANALYSIS RESULTS:
{tool_results}

Generate a detailed markdown report with these sections:
1. **Executive Summary** - Brief overview of findings
2. **Attack Timeline** - Chronological sequence of events  
3. **Technical Findings** - Detailed technical analysis
4. **Indicators of Compromise (IOCs)** - IPs, domains, hashes, etc.
5. **Impact Assessment** - What was affected/exposed
6. **Recommendations** - Remediation steps

Use proper markdown formatting with headers, bullet points, and code blocks where appropriate.'''
    
    def __init__(self, config: dict):
        self.config = config
        self.current_model = config.get("current_model", "gpt4o")
        self.model_config = config.get("models", {}).get(self.current_model, {})
        self.provider = self._create_provider()
    
    def _create_provider(self) -> BaseLLMProvider:
        """Create the appropriate provider based on config."""
        provider_type = self.model_config.get("provider", "openai")
        
        providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "vllm_api": VLLMProvider
        }
        
        if provider_type not in providers:
            raise ValueError(f"Unknown provider: {provider_type}")
        
        return providers[provider_type](self.model_config)
    
    def switch_model(self, model_name: str):
        """Hot-swap to a different model."""
        if model_name not in self.config.get("models", {}):
            raise ValueError(f"Unknown model: {model_name}")
        
        self.current_model = model_name
        self.model_config = self.config["models"][model_name]
        self.provider = self._create_provider()
    
    def _build_tool_prompt(self, tools: dict) -> str:
        """Build the tool-calling system prompt."""
        tools_desc = []
        for name, info in tools.items():
            args_str = ", ".join(f"{k}: {v}" for k, v in info.get("args", {}).items())
            args_str = f"({args_str})" if args_str else "()"
            tools_desc.append(f"  - {name}{args_str}: {info['description']}")
        
        tools_section = "\n".join(tools_desc)
        return self.TOOL_CALL_PROMPT.format(tools=tools_section)
    
    def _parse_tool_response(self, raw_content: str) -> LLMResponse:
        """Parse LLM response for tool calls."""
        response = LLMResponse(raw_content=raw_content)
        
        try:
            # Look for JSON in the response
            json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                response.thought = data.get("thought")
                response.tool_name = data.get("tool_name")
                response.tool_args = data.get("tool_args", {})
                
                # Check if ready to respond (no more tools needed)
                if data.get("ready_to_respond", False) or response.tool_name is None:
                    response.status = "ready"
                else:
                    response.status = "continue"
            else:
                # No JSON found - assume ready to respond
                response.status = "ready"
                
        except json.JSONDecodeError:
            response.status = "ready"
        
        return response
    
    def _parse_response(self, raw_content: str) -> LLMResponse:
        """Parse LLM response into structured format (legacy support)."""
        response = LLMResponse(raw_content=raw_content)
        
        try:
            json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', raw_content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                response.thought = data.get("thought")
                response.analysis = data.get("analysis")
                response.tool_name = data.get("tool_name")
                response.tool_args = data.get("tool_args", {})
                response.request_full_context = data.get("request_full_context", False)
                response.context_step_id = data.get("context_step_id")
                response.status = data.get("status", "continue")
                response.final_report = data.get("final_report")
                response.confidence = data.get("confidence", 0.8)
            else:
                response.analysis = raw_content.strip()
                response.status = "continue"
        except json.JSONDecodeError:
            response.analysis = raw_content.strip()
            response.status = "continue"
        
        return response
    
    def generate_tool_call(self, messages: list[dict], tools: dict) -> LLMResponse:
        """
        Generate a tool call decision from the LLM.
        
        Returns a response indicating which tool to call or if ready to respond.
        """
        system_prompt = self._build_tool_prompt(tools)
        
        try:
            raw_content = self.provider.generate(messages, system_prompt)
            return self._parse_tool_response(raw_content)
        except Exception as e:
            return LLMResponse(
                raw_content="",
                parse_error=f"LLM error: {str(e)}",
                status="ready"
            )
    
    def generate_synthesis(
        self, 
        user_question: str, 
        tool_results: list[dict],
        is_final_report: bool = False
    ) -> str:
        """
        Generate a synthesized response based on tool results.
        
        Args:
            user_question: The original user question
            tool_results: List of {tool_name, result} dicts
            is_final_report: If True, generates a formal report
        
        Returns:
            Markdown-formatted response string
        """
        # Format tool results
        results_text = ""
        for i, result in enumerate(tool_results, 1):
            results_text += f"\n### Tool {i}: {result['tool_name']}\n"
            results_text += f"```\n{result['result'][:2000]}\n```\n"
        
        if is_final_report:
            prompt = self.REPORT_PROMPT.format(tool_results=results_text)
        else:
            prompt = self.SYNTHESIS_PROMPT.format(
                tool_results=results_text,
                user_question=user_question
            )
        
        messages = [{"role": "user", "content": "Generate the response."}]
        
        try:
            return self.provider.generate(messages, prompt)
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def generate_title(self, user_question: str, response_summary: str) -> str:
        """
        Generate a short title for the conversation.
        
        Args:
            user_question: The user's first question
            response_summary: Summary of the agent's response
        
        Returns:
            A short title string (3-6 words)
        """
        prompt = self.TITLE_PROMPT.format(
            user_question=user_question[:200],
            response_summary=response_summary[:300]
        )
        
        messages = [{"role": "user", "content": "Generate the title."}]
        
        try:
            title = self.provider.generate(messages, prompt)
            # Clean up the title - remove quotes, extra whitespace, etc.
            title = title.strip().strip('"\'').strip()
            # Limit length
            if len(title) > 50:
                title = title[:47] + "..."
            return title
        except Exception as e:
            return "PCAP Analysis"
    
    def generate(self, messages: list[dict], tools: dict) -> LLMResponse:
        """
        Generate a response from the LLM (legacy method for compatibility).
        """
        system_prompt = self._build_tool_prompt(tools)
        
        try:
            raw_content = self.provider.generate(messages, system_prompt)
            return self._parse_response(raw_content)
        except Exception as e:
            return LLMResponse(
                raw_content="",
                parse_error=f"LLM error: {str(e)}",
                status="need_input"
            )
    
    def stream_generate(self, messages: list[dict], tools: dict) -> Generator[tuple[str, Optional[LLMResponse]], None, None]:
        """
        Stream response from LLM, yielding tokens and final parsed response.
        """
        system_prompt = self._build_tool_prompt(tools)
        full_content = ""
        
        try:
            for token in self.provider.stream(messages, system_prompt):
                full_content += token
                yield (token, None)
            
            response = self._parse_response(full_content)
            yield ("", response)
        except Exception as e:
            yield ("", LLMResponse(
                raw_content=full_content,
                parse_error=f"LLM error: {str(e)}",
                status="need_input"
            ))
    
    def get_model_info(self) -> dict:
        """Get information about the current model."""
        return {
            "name": self.current_model,
            "model": self.model_config.get("name"),
            "provider": self.model_config.get("provider"),
            "context_window": self.model_config.get("context_window"),
            "safety_buffer": self.model_config.get("safety_buffer")
        }
