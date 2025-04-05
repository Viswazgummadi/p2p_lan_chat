#!/usr/bin/env python3
"""
Utility functions for the P2P LAN Chat System.
"""
import socket
import uuid
import random
import time

def get_local_ip():
    """
    Get the local IP address of this machine.
    
    Returns:
        str: Local IP address
    """
    try:
        # Connect to a public server to determine the local IP used for outgoing connections
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        # Fallback if the above method fails
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"  # Last resort fallback

def generate_peer_id():
    """
    Generate a unique ID for this peer.
    
    Returns:
        str: Unique peer ID
    """
    # Combine UUID with a short random number for readability
    random_part = random.randint(1000, 9999)
    return f"{uuid.uuid4().hex[:8]}-{random_part}"

def is_port_available(port):
    """
    Check if a port is available for use.
    
    Args:
        port (int): Port number to check
        
    Returns:
        bool: True if the port is available, False otherwise
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('', port))
        result = True
    except:
        result = False
    sock.close()
    return result

def find_available_port(start_port=0):
    """
    Find an available port.
    
    Args:
        start_port (int): Starting port number (0 for random)
        
    Returns:
        int: Available port number
    """
    if start_port == 0:
        # Let the OS choose a random available port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port
    else:
        # Try ports starting from start_port
        for port in range(start_port, 65536):
            if is_port_available(port):
                return port
        # If no ports are available, let the OS choose
        return find_available_port(0)
