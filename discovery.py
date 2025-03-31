#!/usr/bin/env python3
"""
Peer discovery functionality for the P2P LAN Chat System.
"""
import socket
import json
import threading
import time

class Discovery:
    """
    Handles peer discovery on the local network using UDP broadcasts.
    """
    def __init__(self, peer, discovery_port=35000, broadcast_interval=30):
        """
        Initialize the discovery service.
        
        Args:
            peer: Reference to the Peer instance
            discovery_port (int): UDP port for discovery broadcasts
            broadcast_interval (int): Seconds between discovery broadcasts
        """
        self.peer = peer
        self.discovery_port = discovery_port
        self.broadcast_interval = broadcast_interval
        self.running = False
        self.threads = []
    
    def start(self):
        """Start the discovery service."""
        self.running = True
        
        # Start broadcast thread
        broadcast_thread = threading.Thread(target=self._broadcast_presence)
        broadcast_thread.daemon = True
        broadcast_thread.start()
        self.threads.append(broadcast_thread)
        
        # Start listener thread
        listener_thread = threading.Thread(target=self._listen_for_peers)
        listener_thread.daemon = True
        listener_thread.start()
        self.threads.append(listener_thread)
    
    def stop(self):
        """Stop the discovery service."""
        self.running = False
        # Threads will exit on their own as they check self.running
    
    def _broadcast_presence(self):
        """Broadcast peer presence on the network."""
        # Create UDP socket for broadcasting
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            while self.running:
                try:
                    # Prepare discovery message
                    discovery_msg = {
                        'type': 'discovery',
                        'peer_id': self.peer.peer_id,
                        'nickname': self.peer.nickname,
                        'ip': self.peer.ip,
                        'port': self.peer.port
                    }
                    
                    # Broadcast the message
                    message = json.dumps(discovery_msg).encode()
                    s.sendto(message, ('<broadcast>', self.discovery_port))
                    
                    # Wait before broadcasting again
                    for _ in range(self.broadcast_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                        
                except Exception as e:
                    print(f"Error broadcasting presence: {e}")
                    # Wait a bit before retrying
                    time.sleep(5)
    
    def _listen_for_peers(self):
        """Listen for peer discovery broadcasts."""
        # Create UDP socket for listening
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', self.discovery_port))
            
            while self.running:
                try:
                    # Set socket timeout so we can check running flag
                    s.settimeout(1)
                    
                    try:
                        # Receive discovery message
                        data, addr = s.recvfrom(1024)
                        
                        # Parse message
                        try:
                            message = json.loads(data.decode())
                            if message.get('type') == 'discovery':
                                peer_id = message.get('peer_id')
                                ip = message.get('ip')
                                port = message.get('port')
                                
                                # Don't connect to self
                                if peer_id == self.peer.peer_id:
                                    continue
                                
                                # Check if already connected
                                already_connected = False
                                with self.peer.peers_lock:
                                    already_connected = peer_id in self.peer.peers
                                
                                if not already_connected:
                                    print(f"Discovered peer {message.get('nickname')} ({peer_id}) at {ip}:{port}")
                                    # Try to connect
                                    self.peer.connect_to_peer(ip, port)
                        except json.JSONDecodeError:
                            # Invalid message
                            pass
                    except socket.timeout:
                        # This is expected, we set a timeout to check running flag
                        pass
                        
                except Exception as e:
                    if self.running:  # Only show error if we're still running
                        print(f"Error listening for peers: {e}")
                        # Wait a bit before retrying
                        time.sleep(5)
