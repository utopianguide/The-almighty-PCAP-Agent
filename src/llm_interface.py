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
    
    def generate(self, messages: list[dict], system_prompt: str) -> str:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    def stream(self, messages: list[dict], system_prompt: str) -> Generator[str, None, None]:
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=0.3,
            stream=True
        )
        
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
    
    SYSTEM_PROMPT_TEMPLATE = '''You are an expert Cyber Security Forensic Analyst. You are investigating a PCAP network capture file to identify security incidents.

OBJECTIVE: Analyze the PCAP file systematically and identify the root cause of any security incidents. Work autonomously, making intelligent decisions about what to investigate next.

AVAILABLE TOOLS:
{tools}

RESPONSE FORMAT:
You MUST respond in valid JSON format with the following structure:
{{
    "thought": "Your reasoning about what you've learned and what to do next",
    "analysis": "A clear summary of your findings for display to the analyst",
    "tool_name": "name_of_tool_to_execute (or null if no tool needed)",
    "tool_args": {{}},  // Arguments for the tool (empty object if no args)
    "request_full_context": false,  // Set to true if you need to see full truncated output
    "context_step_id": null,  // Step ID to load full context from (if request_full_context is true)
    "status": "continue",  // "continue" | "finished" | "need_input"
    "final_report": null,  // Populate only when status is "finished"
    "confidence": 0.8  // Your confidence in current findings (0.0 to 1.0)
}}

INVESTIGATION METHODOLOGY:
1. Start with high-level overview (protocol hierarchy, conversations)
2. Identify anomalies (unusual traffic patterns, suspicious IPs, high volumes)
3. Drill down into suspicious activity (specific protocols, conversations)
4. Follow the evidence chain (timeline of attack, lateral movement)
5. Document findings and conclude with a final report

ANALYSIS GUIDELINES:
- Look for signs of: reconnaissance, exploitation, C2 communication, data exfiltration
- Pay attention to: unusual ports, high data volumes, suspicious domains, failed auth attempts
- Consider attack patterns: SQL injection, brute force, malware callbacks, tunneling
- When output is truncated, decide if you need full context or if summary is sufficient

When you have identified the incident with reasonable confidence, set status to "finished" and provide a comprehensive final_report including:
- Attack type and description
- Attacker IP(s) and victim IP(s)
- Timeline of events
- Impact assessment
- Recommended remediation'''
    
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
    
    def _build_system_prompt(self, tools: dict) -> str:
        """Build the system prompt with available tools."""
        tools_desc = []
        for name, info in tools.items():
            args_str = ", ".join(f"{k}: {v}" for k, v in info.get("args", {}).items())
            args_str = f"({args_str})" if args_str else "()"
            tools_desc.append(f"  - {name}{args_str}: {info['description']}")
        
        tools_section = "\n".join(tools_desc)
        return self.SYSTEM_PROMPT_TEMPLATE.format(tools=tools_section)
    
    def _parse_response(self, raw_content: str) -> LLMResponse:
        """Parse LLM response into structured format."""
        response = LLMResponse(raw_content=raw_content)
        
        # Try to extract JSON from the response
        try:
            # Look for JSON block in the response
            json_match = re.search(r'\{[\s\S]*\}', raw_content)
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
                response.parse_error = "No JSON found in response"
        except json.JSONDecodeError as e:
            response.parse_error = f"JSON parse error: {str(e)}"
        
        return response
    
    def generate(self, messages: list[dict], tools: dict) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: Conversation history
            tools: Available tools dictionary
        
        Returns:
            Structured LLMResponse
        """
        system_prompt = self._build_system_prompt(tools)
        
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
        
        Yields tuples of (token, response) where response is only set on final yield.
        """
        system_prompt = self._build_system_prompt(tools)
        full_content = ""
        
        try:
            for token in self.provider.stream(messages, system_prompt):
                full_content += token
                yield (token, None)
            
            # Final yield with parsed response
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

