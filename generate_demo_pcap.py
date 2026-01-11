#!/usr/bin/env python3
"""
Demo PCAP Generator
====================
Generates a realistic attack scenario PCAP for demonstrating 
the PCAP Forensic Analysis Agent.

Scenario: FTP Brute Force Attack + Data Exfiltration
- Attacker (192.168.1.105) scans the victim (10.0.0.5)
- Multiple failed FTP login attempts (brute force)
- Successful login after several attempts
- Large file exfiltration via FTP
- Suspicious DNS queries to exfiltration domain

Requirements:
    pip install scapy
"""

from scapy.all import (
    Ether, IP, TCP, UDP, DNS, DNSQR, DNSRR, Raw,
    wrpcap, RandShort
)
import random
import time
from datetime import datetime, timedelta

# Configuration
ATTACKER_IP = "192.168.1.105"
ATTACKER_MAC = "aa:bb:cc:dd:ee:01"
VICTIM_IP = "10.0.0.5"
VICTIM_MAC = "aa:bb:cc:dd:ee:02"
DNS_SERVER_IP = "8.8.8.8"
EXFIL_DOMAIN = "data-backup-service.ru"
EXFIL_IP = "185.143.223.47"

# FTP Credentials for brute force
USERNAMES = ["admin", "root", "administrator", "ftp", "user", "backup"]
PASSWORDS = ["123456", "password", "admin", "root", "letmein", "pass123", 
             "admin123", "welcome", "qwerty", "Backup2024!"]  # Last one is "correct"

packets = []
current_time = datetime.now() - timedelta(hours=1)

def get_timestamp():
    """Get incrementing timestamp."""
    global current_time
    current_time += timedelta(milliseconds=random.randint(10, 500))
    return current_time.timestamp()

def create_tcp_handshake(src_ip, dst_ip, src_mac, dst_mac, sport, dport):
    """Create TCP 3-way handshake."""
    seq = random.randint(1000, 100000)
    ack = random.randint(1000, 100000)
    
    # SYN
    syn = Ether(src=src_mac, dst=dst_mac) / \
          IP(src=src_ip, dst=dst_ip) / \
          TCP(sport=sport, dport=dport, flags="S", seq=seq)
    syn.time = get_timestamp()
    packets.append(syn)
    
    # SYN-ACK
    syn_ack = Ether(src=dst_mac, dst=src_mac) / \
              IP(src=dst_ip, dst=src_ip) / \
              TCP(sport=dport, dport=sport, flags="SA", seq=ack, ack=seq+1)
    syn_ack.time = get_timestamp()
    packets.append(syn_ack)
    
    # ACK
    ack_pkt = Ether(src=src_mac, dst=dst_mac) / \
              IP(src=src_ip, dst=dst_ip) / \
              TCP(sport=sport, dport=dport, flags="A", seq=seq+1, ack=ack+1)
    ack_pkt.time = get_timestamp()
    packets.append(ack_pkt)
    
    return seq + 1, ack + 1

def create_ftp_exchange(sport, seq, ack, username, password, success=False):
    """Create FTP login attempt."""
    # Server banner
    banner = Ether(src=VICTIM_MAC, dst=ATTACKER_MAC) / \
             IP(src=VICTIM_IP, dst=ATTACKER_IP) / \
             TCP(sport=21, dport=sport, flags="PA", seq=ack, ack=seq) / \
             Raw(load=b"220 FTP Server Ready\r\n")
    banner.time = get_timestamp()
    packets.append(banner)
    ack += len(b"220 FTP Server Ready\r\n")
    
    # USER command
    user_cmd = Ether(src=ATTACKER_MAC, dst=VICTIM_MAC) / \
               IP(src=ATTACKER_IP, dst=VICTIM_IP) / \
               TCP(sport=sport, dport=21, flags="PA", seq=seq, ack=ack) / \
               Raw(load=f"USER {username}\r\n".encode())
    user_cmd.time = get_timestamp()
    packets.append(user_cmd)
    seq += len(f"USER {username}\r\n")
    
    # Server response
    user_resp = Ether(src=VICTIM_MAC, dst=ATTACKER_MAC) / \
                IP(src=VICTIM_IP, dst=ATTACKER_IP) / \
                TCP(sport=21, dport=sport, flags="PA", seq=ack, ack=seq) / \
                Raw(load=b"331 Password required\r\n")
    user_resp.time = get_timestamp()
    packets.append(user_resp)
    ack += len(b"331 Password required\r\n")
    
    # PASS command
    pass_cmd = Ether(src=ATTACKER_MAC, dst=VICTIM_MAC) / \
               IP(src=ATTACKER_IP, dst=VICTIM_IP) / \
               TCP(sport=sport, dport=21, flags="PA", seq=seq, ack=ack) / \
               Raw(load=f"PASS {password}\r\n".encode())
    pass_cmd.time = get_timestamp()
    packets.append(pass_cmd)
    seq += len(f"PASS {password}\r\n")
    
    # Login result
    if success:
        resp = b"230 Login successful\r\n"
    else:
        resp = b"530 Login incorrect\r\n"
    
    login_resp = Ether(src=VICTIM_MAC, dst=ATTACKER_MAC) / \
                 IP(src=VICTIM_IP, dst=ATTACKER_IP) / \
                 TCP(sport=21, dport=sport, flags="PA", seq=ack, ack=seq) / \
                 Raw(load=resp)
    login_resp.time = get_timestamp()
    packets.append(login_resp)
    
    return seq, ack + len(resp)

def create_ftp_data_transfer(sport, dport):
    """Simulate large file transfer via FTP data channel."""
    seq, ack = create_tcp_handshake(
        VICTIM_IP, ATTACKER_IP, VICTIM_MAC, ATTACKER_MAC, dport, sport
    )
    
    # Simulate transferring chunks of a large file
    file_content = b"CONFIDENTIAL DATABASE DUMP\n" + b"=" * 50 + b"\n"
    file_content += b"customer_id,name,ssn,credit_card,password_hash\n"
    
    for i in range(50):
        row = f"{i+1},User{i+1},XXX-XX-{1000+i},{4000_0000_0000_0000 + i},hash{i}\n"
        file_content += row.encode()
    
    # Send data in chunks
    chunk_size = 1460
    for i in range(0, len(file_content), chunk_size):
        chunk = file_content[i:i+chunk_size]
        data_pkt = Ether(src=VICTIM_MAC, dst=ATTACKER_MAC) / \
                   IP(src=VICTIM_IP, dst=ATTACKER_IP) / \
                   TCP(sport=dport, dport=sport, flags="PA", seq=seq, ack=ack) / \
                   Raw(load=chunk)
        data_pkt.time = get_timestamp()
        packets.append(data_pkt)
        seq += len(chunk)
        
        # ACK from attacker
        ack_pkt = Ether(src=ATTACKER_MAC, dst=VICTIM_MAC) / \
                  IP(src=ATTACKER_IP, dst=VICTIM_IP) / \
                  TCP(sport=sport, dport=dport, flags="A", seq=ack, ack=seq)
        ack_pkt.time = get_timestamp()
        packets.append(ack_pkt)

def create_dns_query(domain, response_ip):
    """Create DNS query and response."""
    dns_id = random.randint(1, 65535)
    
    # Query
    query = Ether(src=ATTACKER_MAC, dst="ff:ff:ff:ff:ff:ff") / \
            IP(src=ATTACKER_IP, dst=DNS_SERVER_IP) / \
            UDP(sport=random.randint(49152, 65535), dport=53) / \
            DNS(id=dns_id, qd=DNSQR(qname=domain))
    query.time = get_timestamp()
    packets.append(query)
    
    # Response
    response = Ether(src="ff:ff:ff:ff:ff:ff", dst=ATTACKER_MAC) / \
               IP(src=DNS_SERVER_IP, dst=ATTACKER_IP) / \
               UDP(sport=53, dport=query[UDP].sport) / \
               DNS(id=dns_id, qr=1, qd=DNSQR(qname=domain),
                   an=DNSRR(rrname=domain, ttl=300, rdata=response_ip))
    response.time = get_timestamp()
    packets.append(response)

def create_port_scan():
    """Create initial port scan activity."""
    common_ports = [21, 22, 23, 25, 80, 443, 445, 3389, 8080]
    
    for port in common_ports:
        sport = random.randint(49152, 65535)
        seq = random.randint(1000, 100000)
        
        # SYN
        syn = Ether(src=ATTACKER_MAC, dst=VICTIM_MAC) / \
              IP(src=ATTACKER_IP, dst=VICTIM_IP) / \
              TCP(sport=sport, dport=port, flags="S", seq=seq)
        syn.time = get_timestamp()
        packets.append(syn)
        
        # Response based on port
        if port in [21, 22, 80]:  # Open ports
            resp = Ether(src=VICTIM_MAC, dst=ATTACKER_MAC) / \
                   IP(src=VICTIM_IP, dst=ATTACKER_IP) / \
                   TCP(sport=port, dport=sport, flags="SA", seq=random.randint(1000, 100000), ack=seq+1)
        else:  # Closed ports
            resp = Ether(src=VICTIM_MAC, dst=ATTACKER_MAC) / \
                   IP(src=VICTIM_IP, dst=ATTACKER_IP) / \
                   TCP(sport=port, dport=sport, flags="RA", seq=0, ack=seq+1)
        resp.time = get_timestamp()
        packets.append(resp)

def main():
    print("=" * 60)
    print("PCAP Demo Generator - Attack Scenario")
    print("=" * 60)
    print(f"\nAttacker: {ATTACKER_IP}")
    print(f"Victim:   {VICTIM_IP}")
    print(f"Scenario: FTP Brute Force + Data Exfiltration\n")
    
    # Phase 1: Port Scan
    print("[1/5] Generating port scan traffic...")
    create_port_scan()
    
    # Phase 2: Suspicious DNS lookups
    print("[2/5] Generating suspicious DNS queries...")
    create_dns_query(EXFIL_DOMAIN, EXFIL_IP)
    create_dns_query("malware-c2.net", "203.0.113.66")
    
    # Phase 3: FTP Brute Force (multiple failed attempts)
    print("[3/5] Generating FTP brute force attempts...")
    attempt = 0
    for username in USERNAMES[:3]:  # Try 3 usernames
        for password in PASSWORDS[:8]:  # Try 8 passwords each
            attempt += 1
            sport = 40000 + attempt
            seq, ack = create_tcp_handshake(
                ATTACKER_IP, VICTIM_IP, ATTACKER_MAC, VICTIM_MAC, sport, 21
            )
            create_ftp_exchange(sport, seq, ack, username, password, success=False)
    
    print(f"    Generated {attempt} failed login attempts")
    
    # Phase 4: Successful login
    print("[4/5] Generating successful FTP login...")
    sport = 41000
    seq, ack = create_tcp_handshake(
        ATTACKER_IP, VICTIM_IP, ATTACKER_MAC, VICTIM_MAC, sport, 21
    )
    create_ftp_exchange(sport, seq, ack, "backup", "Backup2024!", success=True)
    
    # Add RETR command for file download
    retr_cmd = Ether(src=ATTACKER_MAC, dst=VICTIM_MAC) / \
               IP(src=ATTACKER_IP, dst=VICTIM_IP) / \
               TCP(sport=sport, dport=21, flags="PA") / \
               Raw(load=b"RETR confidential_db_dump.sql\r\n")
    retr_cmd.time = get_timestamp()
    packets.append(retr_cmd)
    
    # Phase 5: Data exfiltration
    print("[5/5] Generating data exfiltration traffic...")
    create_ftp_data_transfer(41001, 20)
    
    # Write to file
    output_file = "demo_attack.pcap"
    print(f"\nWriting {len(packets)} packets to {output_file}...")
    wrpcap(output_file, packets)
    
    print("\n" + "=" * 60)
    print("✓ PCAP file generated successfully!")
    print(f"  File: {output_file}")
    print(f"  Packets: {len(packets)}")
    print("\nAttack Timeline:")
    print("  1. Initial reconnaissance (port scan)")
    print("  2. Suspicious DNS queries to external domains")
    print(f"  3. FTP brute force ({attempt} failed attempts)")
    print("  4. Successful login with stolen credentials")
    print("  5. Exfiltration of confidential_db_dump.sql")
    print("=" * 60)

if __name__ == "__main__":
    main()
