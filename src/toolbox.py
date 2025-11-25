"""
Toolbox - The Tshark Wrapper Functions
=======================================
Provides structured, safe Python functions for running Tshark commands.
Prevents hallucinated flags and ensures input sanitization.
"""

import subprocess
import shutil
import re
import time
from typing import Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    command: str = ""
    truncated: bool = False
    total_lines: int = 0


class TsharkNotFoundError(Exception):
    """Raised when tshark executable is not found."""
    pass


class Toolbox:
    """
    Collection of Tshark-based forensic analysis tools.
    
    Each tool is a Python function that:
    1. Validates inputs
    2. Constructs a safe Tshark command
    3. Executes and captures output
    4. Returns structured results
    """
    
    # Valid display filter operators for sanitization
    VALID_FILTER_CHARS = re.compile(r'^[a-zA-Z0-9_.\-\s\(\)\[\]<>=!&|,\"\':/]+$')
    
    def __init__(self, pcap_file: str, config: dict):
        self.pcap_file = pcap_file
        self.config = config
        self.tshark_path = self._find_tshark()
        self.timeout = config.get("tshark", {}).get("timeout", 120)
        self.truncate_threshold = config.get("output", {}).get("truncate_threshold", 100)
        self.truncate_preview = config.get("output", {}).get("truncate_preview_lines", 50)
        
        # Verify PCAP file exists
        if not Path(pcap_file).exists():
            raise FileNotFoundError(f"PCAP file not found: {pcap_file}")
    
    def _find_tshark(self) -> str:
        """Locate tshark executable."""
        # Check config first
        config_path = self.config.get("tshark", {}).get("path", "")
        if config_path and Path(config_path).exists():
            return config_path
        
        # Try common locations
        tshark = shutil.which("tshark")
        if tshark:
            return tshark
        
        # Windows common paths
        windows_paths = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
        ]
        for path in windows_paths:
            if Path(path).exists():
                return path
        
        raise TsharkNotFoundError(
            "Tshark not found. Please install Wireshark or set the path in config.yaml"
        )
    
    def _sanitize_filter(self, display_filter: str) -> str:
        """Sanitize display filter to prevent injection."""
        if not display_filter:
            return ""
        
        # Check for valid characters
        if not self.VALID_FILTER_CHARS.match(display_filter):
            raise ValueError(f"Invalid characters in display filter: {display_filter}")
        
        # Block dangerous patterns
        dangerous = ["$(", "`", ";", "&&", "||", "|", ">", "<", "\\n", "\\r"]
        for pattern in dangerous:
            if pattern in display_filter:
                raise ValueError(f"Dangerous pattern in display filter: {pattern}")
        
        return display_filter.strip()
    
    def _run_tshark(self, args: list[str], description: str = "") -> ToolResult:
        """Execute tshark with given arguments."""
        cmd = [self.tshark_path] + args
        cmd_str = " ".join(cmd)
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            execution_time = time.time() - start_time
            
            output = result.stdout
            error = result.stderr if result.returncode != 0 else None
            
            # Check for truncation
            lines = output.split("\n")
            total_lines = len(lines)
            truncated = False
            
            if total_lines > self.truncate_threshold:
                truncated = True
                preview_lines = lines[:self.truncate_preview]
                output = "\n".join(preview_lines)
                output += f"\n\n[... {total_lines - self.truncate_preview} more lines truncated ...]"
                output += f"\n[SYSTEM: Output truncated. Request full context if needed for detailed analysis.]"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=error,
                execution_time=execution_time,
                command=cmd_str,
                truncated=truncated,
                total_lines=total_lines
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {self.timeout} seconds",
                execution_time=self.timeout,
                command=cmd_str
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start_time,
                command=cmd_str
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TOOL DEFINITIONS - Available to the Agent
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_pcap_info(self) -> ToolResult:
        """
        Get basic information about the PCAP file.
        Shows file size, packet count, capture duration, etc.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", "capinfos,*"],
            "Getting PCAP file information"
        )
    
    def get_protocol_hierarchy(self) -> ToolResult:
        """
        Get protocol hierarchy statistics.
        Shows distribution of protocols (e.g., 80% HTTP, 10% DNS).
        Useful for initial overview of traffic composition.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", "io,phs"],
            "Analyzing protocol hierarchy"
        )
    
    def get_ip_conversations(self) -> ToolResult:
        """
        Get IP conversation statistics.
        Shows who is talking to whom and data volumes.
        Essential for identifying top talkers and potential attackers.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", "conv,ip"],
            "Analyzing IP conversations"
        )
    
    def get_tcp_conversations(self) -> ToolResult:
        """
        Get TCP conversation statistics.
        Shows TCP connections with ports, useful for service identification.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", "conv,tcp"],
            "Analyzing TCP conversations"
        )
    
    def get_udp_conversations(self) -> ToolResult:
        """
        Get UDP conversation statistics.
        Shows UDP communications, useful for DNS, VOIP, gaming traffic.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", "conv,udp"],
            "Analyzing UDP conversations"
        )
    
    def get_endpoints(self, protocol: str = "ip") -> ToolResult:
        """
        Get endpoint statistics for a protocol.
        
        Args:
            protocol: Protocol to analyze (ip, tcp, udp, eth)
        """
        valid_protocols = ["ip", "tcp", "udp", "eth", "ipv6"]
        if protocol not in valid_protocols:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid protocol. Choose from: {valid_protocols}"
            )
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", f"endpoints,{protocol}"],
            f"Analyzing {protocol} endpoints"
        )
    
    def get_http_requests(self) -> ToolResult:
        """
        Extract HTTP request information.
        Shows URIs, methods, and source IPs.
        Critical for web attack analysis (SQLi, XSS, etc.).
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "http.request",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "http.request.method",
             "-e", "http.host",
             "-e", "http.request.uri"],
            "Extracting HTTP requests"
        )
    
    def get_http_responses(self) -> ToolResult:
        """
        Extract HTTP response information.
        Shows response codes and content types.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "http.response",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "http.response.code",
             "-e", "http.content_type"],
            "Extracting HTTP responses"
        )
    
    def get_dns_queries(self) -> ToolResult:
        """
        Extract DNS query information.
        Shows queried domains and source IPs.
        Useful for C2 detection, DNS tunneling, exfiltration.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "dns.flags.response == 0",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "dns.qry.name",
             "-e", "dns.qry.type"],
            "Extracting DNS queries"
        )
    
    def get_dns_responses(self) -> ToolResult:
        """
        Extract DNS response information.
        Shows resolved addresses for domains.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "dns.flags.response == 1",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "dns.qry.name",
             "-e", "dns.a",
             "-e", "dns.aaaa",
             "-e", "dns.resp.type"],
            "Extracting DNS responses"
        )
    
    def get_ftp_commands(self) -> ToolResult:
        """
        Extract FTP commands.
        Shows FTP operations including login attempts and file transfers.
        Critical for data exfiltration analysis.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "ftp.request.command",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "ftp.request.command",
             "-e", "ftp.request.arg"],
            "Extracting FTP commands"
        )
    
    def get_ftp_responses(self) -> ToolResult:
        """
        Extract FTP server responses.
        Shows login success/failure and transfer status.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "ftp.response.code",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ftp.response.code",
             "-e", "ftp.response.arg"],
            "Extracting FTP responses"
        )
    
    def get_smtp_traffic(self) -> ToolResult:
        """
        Extract SMTP email traffic.
        Shows email senders, recipients, and commands.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "smtp",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "smtp.req.command",
             "-e", "smtp.req.parameter"],
            "Extracting SMTP traffic"
        )
    
    def get_tls_handshakes(self) -> ToolResult:
        """
        Extract TLS/SSL handshake information.
        Shows server names (SNI), cipher suites, and certificates.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "tls.handshake.type == 1",
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "tls.handshake.extensions_server_name",
             "-e", "tls.handshake.ciphersuite"],
            "Extracting TLS handshakes"
        )
    
    def get_suspicious_ports(self) -> ToolResult:
        """
        Find traffic on suspicious/unusual ports.
        Looks for non-standard ports that might indicate malware or tunneling.
        """
        # Common legitimate ports to exclude
        exclude_ports = "!(tcp.port == 80 || tcp.port == 443 || tcp.port == 22 || tcp.port == 21 || tcp.port == 25 || tcp.port == 53 || tcp.port == 110 || tcp.port == 143 || tcp.port == 993 || tcp.port == 995 || tcp.port == 3389)"
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", exclude_ports, "-q", "-z", "conv,tcp"],
            "Finding traffic on suspicious ports"
        )
    
    def filter_packets(self, display_filter: str, limit: int = 50) -> ToolResult:
        """
        Filter packets using Wireshark display filter syntax.
        
        Args:
            display_filter: Wireshark display filter (e.g., "ip.addr == 192.168.1.5")
            limit: Maximum packets to return (default 50)
        
        Examples:
            - "ip.addr == 192.168.1.5" - All packets involving this IP
            - "tcp.port == 4444" - Potential reverse shell port
            - "http.request.uri contains 'SELECT'" - SQL injection attempts
            - "dns.qry.name contains '.xyz'" - Suspicious TLD queries
        """
        try:
            safe_filter = self._sanitize_filter(display_filter)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))
        
        limit = min(max(1, limit), 1000)  # Clamp between 1 and 1000
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", safe_filter, "-c", str(limit)],
            f"Filtering packets: {display_filter}"
        )
    
    def extract_fields(
        self, 
        display_filter: str, 
        fields: list[str],
        limit: int = 100
    ) -> ToolResult:
        """
        Extract specific fields from filtered packets.
        
        Args:
            display_filter: Wireshark display filter
            fields: List of field names to extract
            limit: Maximum rows to return
        
        Common fields:
            - frame.time, frame.number, frame.len
            - ip.src, ip.dst, ip.proto
            - tcp.srcport, tcp.dstport, tcp.flags
            - http.request.uri, http.request.method, http.host
            - dns.qry.name, dns.a
        """
        try:
            safe_filter = self._sanitize_filter(display_filter)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))
        
        # Sanitize field names
        valid_field_pattern = re.compile(r'^[a-zA-Z0-9_.]+$')
        safe_fields = []
        for field in fields[:20]:  # Max 20 fields
            if valid_field_pattern.match(field):
                safe_fields.append(field)
        
        if not safe_fields:
            return ToolResult(
                success=False,
                output="",
                error="No valid fields specified"
            )
        
        limit = min(max(1, limit), 1000)
        
        args = ["-r", self.pcap_file, "-T", "fields"]
        if safe_filter:
            args.extend(["-Y", safe_filter])
        for field in safe_fields:
            args.extend(["-e", field])
        args.extend(["-c", str(limit)])
        
        return self._run_tshark(args, f"Extracting fields: {safe_fields}")
    
    def get_streams_summary(self, protocol: str = "tcp") -> ToolResult:
        """
        Get summary of protocol streams.
        Useful for identifying distinct sessions/connections.
        
        Args:
            protocol: tcp or udp
        """
        if protocol not in ["tcp", "udp"]:
            return ToolResult(
                success=False,
                output="",
                error="Protocol must be 'tcp' or 'udp'"
            )
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", f"follow,{protocol},ascii,0"],
            f"Getting {protocol} stream summary"
        )
    
    def follow_stream(self, stream_index: int, protocol: str = "tcp") -> ToolResult:
        """
        Follow a specific protocol stream to see the conversation.
        
        Args:
            stream_index: The stream number to follow
            protocol: tcp or udp
        """
        if protocol not in ["tcp", "udp"]:
            return ToolResult(
                success=False,
                output="",
                error="Protocol must be 'tcp' or 'udp'"
            )
        
        stream_index = max(0, int(stream_index))
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", f"follow,{protocol},ascii,{stream_index}"],
            f"Following {protocol} stream {stream_index}"
        )
    
    def get_expert_info(self) -> ToolResult:
        """
        Get Wireshark expert information/warnings.
        Shows network anomalies, errors, and warnings detected.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", "expert"],
            "Getting expert analysis"
        )
    
    def get_io_stats(self, interval: int = 1) -> ToolResult:
        """
        Get I/O statistics over time.
        Shows traffic volume distribution over the capture period.
        
        Args:
            interval: Time interval in seconds for statistics
        """
        interval = max(1, min(interval, 60))
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-q", "-z", f"io,stat,{interval}"],
            f"Getting I/O statistics (interval: {interval}s)"
        )
    
    def search_payload(self, search_string: str, protocol: str = "") -> ToolResult:
        """
        Search for a string in packet payloads.
        
        Args:
            search_string: String to search for
            protocol: Optional protocol filter (http, ftp, smtp, etc.)
        """
        # Sanitize search string
        safe_string = re.sub(r'[^\w\s\-_./]', '', search_string)[:100]
        
        filter_expr = f'frame contains "{safe_string}"'
        if protocol:
            protocol = re.sub(r'[^a-zA-Z]', '', protocol)
            filter_expr = f'{protocol} && frame contains "{safe_string}"'
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", filter_expr,
             "-T", "fields",
             "-e", "frame.number",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst"],
            f"Searching for: {safe_string}"
        )
    
    def get_credentials(self) -> ToolResult:
        """
        Search for potential cleartext credentials in common protocols.
        Checks FTP, HTTP Basic Auth, SMTP, POP3, IMAP.
        """
        # Look for authentication-related traffic
        auth_filter = (
            "(ftp.request.command == USER || ftp.request.command == PASS || "
            "http.authorization || smtp.req.command == AUTH || "
            "pop.request.command == USER || pop.request.command == PASS)"
        )
        
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", auth_filter,
             "-T", "fields",
             "-e", "frame.time",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "ftp.request.command",
             "-e", "ftp.request.arg",
             "-e", "http.authorization"],
            "Searching for credentials"
        )
    
    def detect_port_scan(self) -> ToolResult:
        """
        Detect potential port scanning activity.
        Looks for many SYN packets from same source to different ports.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "tcp.flags.syn == 1 && tcp.flags.ack == 0",
             "-T", "fields",
             "-e", "ip.src",
             "-e", "ip.dst",
             "-e", "tcp.dstport"],
            "Detecting port scan activity"
        )
    
    def get_user_agents(self) -> ToolResult:
        """
        Extract HTTP User-Agent strings.
        Useful for identifying tools, malware, or suspicious clients.
        """
        return self._run_tshark(
            ["-r", self.pcap_file, "-Y", "http.user_agent",
             "-T", "fields",
             "-e", "ip.src",
             "-e", "http.user_agent"],
            "Extracting User-Agents"
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TOOL REGISTRY - For Agent Tool Selection
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_available_tools(self) -> dict:
        """Return registry of all available tools with descriptions."""
        return {
            "get_pcap_info": {
                "description": "Get basic PCAP file information (size, packets, duration)",
                "args": {},
                "category": "overview"
            },
            "get_protocol_hierarchy": {
                "description": "Get protocol distribution statistics (% HTTP, DNS, etc.)",
                "args": {},
                "category": "overview"
            },
            "get_ip_conversations": {
                "description": "Get IP-to-IP conversation statistics with data volumes",
                "args": {},
                "category": "conversations"
            },
            "get_tcp_conversations": {
                "description": "Get TCP conversation statistics with ports",
                "args": {},
                "category": "conversations"
            },
            "get_udp_conversations": {
                "description": "Get UDP conversation statistics",
                "args": {},
                "category": "conversations"
            },
            "get_endpoints": {
                "description": "Get endpoint statistics for a protocol",
                "args": {"protocol": "ip|tcp|udp|eth (default: ip)"},
                "category": "overview"
            },
            "get_http_requests": {
                "description": "Extract HTTP requests (URIs, methods, hosts)",
                "args": {},
                "category": "http"
            },
            "get_http_responses": {
                "description": "Extract HTTP responses (status codes, content types)",
                "args": {},
                "category": "http"
            },
            "get_dns_queries": {
                "description": "Extract DNS queries (domains being looked up)",
                "args": {},
                "category": "dns"
            },
            "get_dns_responses": {
                "description": "Extract DNS responses (resolved addresses)",
                "args": {},
                "category": "dns"
            },
            "get_ftp_commands": {
                "description": "Extract FTP commands (login, file operations)",
                "args": {},
                "category": "ftp"
            },
            "get_ftp_responses": {
                "description": "Extract FTP server responses",
                "args": {},
                "category": "ftp"
            },
            "get_smtp_traffic": {
                "description": "Extract SMTP email traffic",
                "args": {},
                "category": "email"
            },
            "get_tls_handshakes": {
                "description": "Extract TLS/SSL handshake info (SNI, ciphers)",
                "args": {},
                "category": "encryption"
            },
            "get_suspicious_ports": {
                "description": "Find traffic on non-standard/suspicious ports",
                "args": {},
                "category": "detection"
            },
            "filter_packets": {
                "description": "Filter packets using Wireshark display filter",
                "args": {
                    "display_filter": "Wireshark filter syntax",
                    "limit": "Max packets (default: 50)"
                },
                "category": "analysis"
            },
            "extract_fields": {
                "description": "Extract specific fields from filtered packets",
                "args": {
                    "display_filter": "Wireshark filter",
                    "fields": "List of field names",
                    "limit": "Max rows (default: 100)"
                },
                "category": "analysis"
            },
            "follow_stream": {
                "description": "Follow a specific TCP/UDP stream conversation",
                "args": {
                    "stream_index": "Stream number",
                    "protocol": "tcp|udp (default: tcp)"
                },
                "category": "analysis"
            },
            "get_expert_info": {
                "description": "Get Wireshark expert warnings and anomalies",
                "args": {},
                "category": "detection"
            },
            "get_io_stats": {
                "description": "Get I/O statistics over time",
                "args": {"interval": "Time interval in seconds (default: 1)"},
                "category": "overview"
            },
            "search_payload": {
                "description": "Search for string in packet payloads",
                "args": {
                    "search_string": "String to find",
                    "protocol": "Optional protocol filter"
                },
                "category": "analysis"
            },
            "get_credentials": {
                "description": "Search for cleartext credentials",
                "args": {},
                "category": "detection"
            },
            "detect_port_scan": {
                "description": "Detect potential port scanning activity",
                "args": {},
                "category": "detection"
            },
            "get_user_agents": {
                "description": "Extract HTTP User-Agent strings",
                "args": {},
                "category": "http"
            }
        }
    
    def execute_tool(self, tool_name: str, args: dict = None) -> ToolResult:
        """
        Execute a tool by name with given arguments.
        Used by the agent to call tools dynamically.
        """
        args = args or {}
        
        tool_map = {
            "get_pcap_info": self.get_pcap_info,
            "get_protocol_hierarchy": self.get_protocol_hierarchy,
            "get_ip_conversations": self.get_ip_conversations,
            "get_tcp_conversations": self.get_tcp_conversations,
            "get_udp_conversations": self.get_udp_conversations,
            "get_endpoints": self.get_endpoints,
            "get_http_requests": self.get_http_requests,
            "get_http_responses": self.get_http_responses,
            "get_dns_queries": self.get_dns_queries,
            "get_dns_responses": self.get_dns_responses,
            "get_ftp_commands": self.get_ftp_commands,
            "get_ftp_responses": self.get_ftp_responses,
            "get_smtp_traffic": self.get_smtp_traffic,
            "get_tls_handshakes": self.get_tls_handshakes,
            "get_suspicious_ports": self.get_suspicious_ports,
            "filter_packets": self.filter_packets,
            "extract_fields": self.extract_fields,
            "follow_stream": self.follow_stream,
            "get_expert_info": self.get_expert_info,
            "get_io_stats": self.get_io_stats,
            "search_payload": self.search_payload,
            "get_credentials": self.get_credentials,
            "detect_port_scan": self.detect_port_scan,
            "get_user_agents": self.get_user_agents,
        }
        
        if tool_name not in tool_map:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}. Available: {list(tool_map.keys())}"
            )
        
        try:
            func = tool_map[tool_name]
            # Get function signature and filter valid args
            import inspect
            sig = inspect.signature(func)
            valid_args = {k: v for k, v in args.items() if k in sig.parameters}
            return func(**valid_args)
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution error: {str(e)}"
            )

