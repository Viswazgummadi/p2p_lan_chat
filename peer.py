#!/usr/bin/env python3
"""
Core peer functionality for the P2P LAN Chat System with File Sharing.
Handles networking, connections, and peer management.
"""
import socket
import threading
import json
import time
import os
from message_handler import MessageHandler
from file_handler import FileHandler
from discovery import Discovery
from utils import get_local_ip, generate_peer_id

class Peer:
    """
    Manages the peer-to-peer connections and communication.
    Acts as both server (listening for connections) and client (connecting to peers).
    """
    def __init__(self, nickname, port=0):
        """
        Initialize the peer with a nickname and optional port.
        
        Args:
            nickname (str): User's nickname for identification
            port (int): Port to listen on (0 = random available port)
        """
        self.nickname = nickname
        self.peer_id = generate_peer_id()
        self.ip = get_local_ip()
        self.port = port
        self.running = False
        self.server_socket = None
        self.username_to_id = {}  # {username: peer_id}
        self.peer_id_to_username = {}  # {peer_id: username}

        
        # Initialize components
        self.message_handler = MessageHandler(self)
        self.file_handler = FileHandler(self)
        self.discovery = Discovery(self)
        
        # Peer management
        self.peers = {}  # {peer_id: {'socket': socket, 'ip': ip, 'port': port, 'nickname': nickname}}
        self.peers_lock = threading.Lock()
        
        # Message and file handling threads
        self.threads = []
    
    def start(self):
        """Start the peer server and discovery service."""
        # Initialize server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(10)
        
        # Get the assigned port if we used port 0
        _, self.port = self.server_socket.getsockname()
        
        self.running = True
        print(f"Started peer {self.nickname} ({self.peer_id}) on {self.ip}:{self.port}")
        
        # Start listener thread
        listener_thread = threading.Thread(target=self._listen_for_connections)
        listener_thread.daemon = True
        listener_thread.start()
        self.threads.append(listener_thread)
        
        # Start discovery service
        self.discovery.start()
    
    def stop(self):
        """Stop the peer and close all connections."""
        self.running = False
        
        # Close connections to all peers
        with self.peers_lock:
            for peer_id, peer_info in list(self.peers.items()):
                try:
                    if peer_info.get('socket'):
                        peer_info['socket'].close()
                except:
                    pass
            self.peers.clear()
        
        # Stop discovery
        self.discovery.stop()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print(f"Peer {self.nickname} ({self.peer_id}) stopped")
    
    def connect_to_peer(self, ip, port):
        """
        Connect to another peer.
        
        Args:
            ip (str): IP address of the peer
            port (int): Port number of the peer
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Create socket and connect
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)  # 5 second timeout for connection
            client_socket.connect((ip, port))
            
            # Send our information
            handshake_data = {
                'type': 'handshake',
                'peer_id': self.peer_id,
                'nickname': self.nickname,
                'ip': self.ip,
                'port': self.port
            }
            client_socket.sendall(json.dumps(handshake_data).encode() + b'\n')
            
            # Receive peer information
            peer_data = client_socket.recv(1024).decode().strip()
            try:
                peer_info = json.loads(peer_data)
                if peer_info.get('type') == 'handshake':
                    peer_id = peer_info.get('peer_id')
                    with self.peers_lock:
                        if peer_id in self.peers:
                            # Already connected
                            client_socket.close()
                            return True
                        
                        # Save peer information
                        self.peers[peer_id] = {
                            'socket': client_socket,
                            'ip': ip,
                            'port': port,
                            'nickname': peer_info.get('nickname', 'Unknown')
                        }
                    
                    # Start handler for this connection
                    handler_thread = threading.Thread(
                        target=self._handle_peer,
                        args=(peer_id, client_socket)
                    )
                    handler_thread.daemon = True
                    handler_thread.start()
                    self.threads.append(handler_thread)
                    
                    print(f"Connected to {peer_info.get('nickname')} ({peer_id}) at {ip}:{port}")
                    return True
            except json.JSONDecodeError:
                client_socket.close()
                return False
        except Exception as e:
            print(f"Failed to connect to peer at {ip}:{port}: {e}")
            return False
    
    def disconnect_from_peer(self, peer_id):
        """
        Disconnect from a specific peer.
        
        Args:
            peer_id (str): ID of the peer to disconnect from
        """
        with self.peers_lock:
            if peer_id in self.peers:
                try:
                    self.peers[peer_id]['socket'].close()
                except:
                    pass
                del self.peers[peer_id]
                print(f"Disconnected from peer {peer_id}")
    
    def get_peers(self):
        """Get a list of connected peers."""
        return {
            pid: {
                'nickname': info['nickname'],
                'ip': info['ip'],
                'port': info['port'],
                'status': 'Connected' if info['socket'].fileno() != -1 else 'Disconnected'
            }
            for pid, info in self.peers.items()
        }




    def get_username(self, peer_id):
        return self.peers[peer_id].get('nickname', 'Unknown')



    def find_peer_id(self, identifier):
        """Find peer by username or partial ID"""
        # Check exact username match
        for pid, info in self.peers.items():
            if info['nickname'].lower() == identifier.lower():
                return pid
    
        # Check partial ID match
        for pid in self.peers:
            if pid.startswith(identifier):
                return pid
    
        return None


    def send_message_to_peer(self, peer_id, message):
        """
        Send a text message to a specific peer.
        
        Args:
            peer_id (str): ID of the peer to send the message to
            message (str): Message content
            
        Returns:
            bool: True if the message was sent, False otherwise
        """
        return self.message_handler.send_message(peer_id, message)
    
    def send_message_to_all(self, message):
        """
        Send a text message to all connected peers.
        
        Args:
            message (str): Message content
            
        Returns:
            dict: Dictionary mapping peer_id to success status
        """
        return self.message_handler.send_message_to_all(message)
    
    def send_file_to_peer(self, peer_id, file_path):
        """
        Send a file to a specific peer.
        
        Args:
            peer_id (str): ID of the peer to send the file to
            file_path (str): Path to the file to send
            
        Returns:
            bool: True if the file was sent, False otherwise
        """
        return self.file_handler.send_file(peer_id, file_path)
    
    def _listen_for_connections(self):
        """Listen for incoming connections from other peers."""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                handler_thread = threading.Thread(
                    target=self._handle_incoming_connection,
                    args=(client_socket, addr)
                )
                handler_thread.daemon = True
                handler_thread.start()
                self.threads.append(handler_thread)
            except Exception as e:
                if self.running:  # Only show error if we're still supposed to be running
                    print(f"Error accepting connection: {e}")
                break
    
    def _handle_incoming_connection(self, client_socket, addr):
        """
        Handle an incoming connection from a peer.
        
        Args:
            client_socket (socket.socket): Socket for the connection
            addr (tuple): Address of the connecting peer (ip, port)
        """
        try:
            # Receive peer information
            peer_data = client_socket.recv(1024).decode().strip()
            try:
                peer_info = json.loads(peer_data)
                if peer_info.get('type') == 'handshake':
                    peer_id = peer_info.get('peer_id')
                    
                    # Send our information
                    handshake_response = {
                        'type': 'handshake',
                        'peer_id': self.peer_id,
                        'nickname': self.nickname,
                        'ip': self.ip,
                        'port': self.port
                    }
                    client_socket.sendall(json.dumps(handshake_response).encode() + b'\n')
                    
                    with self.peers_lock:
                        if peer_id in self.peers:
                            # Already connected
                            client_socket.close()
                            return
                        
                        # Save peer information
                        self.peers[peer_id] = {
                            'socket': client_socket,
                            'ip': peer_info.get('ip', addr[0]),
                            'port': peer_info.get('port', addr[1]),
                            'nickname': peer_info.get('nickname', 'Unknown')
                        }
                    
                    print(f"Accepted connection from {peer_info.get('nickname')} ({peer_id}) at {addr}")
                    
                    # Handle communications with this peer
                    self._handle_peer(peer_id, client_socket)
            except json.JSONDecodeError:
                client_socket.close()
        except Exception as e:
            print(f"Error handling incoming connection from {addr}: {e}")
            client_socket.close()
    

    def _update_usernames(self, peer_id, username):
        """Validate and update username mappings"""
        if username in self.username_to_id and self.username_to_id[username] != peer_id:
            raise ValueError(f"Username {username} already exists")
        self.username_to_id[username] = peer_id
        self.peer_id_to_username[peer_id] = username

    def _handle_peer(self, peer_id, client_socket):
        """
        Handle communications with a connected peer.
        
        Args:
            peer_id (str): ID of the peer
            client_socket (socket.socket): Socket for communicating with the peer
        """
        # Set a longer timeout for regular operations
        client_socket.settimeout(60)  # 60 second timeout
        
        try:
            while self.running:
                try:
                    # Receive data
                    data = b''
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    
                    data += chunk
                    
                    # Process received data
                    try:
                        messages = data.decode().strip().split('\n')
                        for message_str in messages:
                            if not message_str:
                                continue
                                
                            message = json.loads(message_str)
                            message_type = message.get('type')
                            
                            if message_type == 'text':
                                # Handle text message
                                self.message_handler.handle_message(peer_id, message)
                            elif message_type == 'file_request':
                                # Handle file transfer request
                                self.file_handler.handle_file_request(peer_id, message)
                            elif message_type == 'file_data':
                                # Handle file data
                                self.file_handler.handle_file_data(peer_id, message)
                            elif message_type == 'file_ack':
                                # Handle file transfer acknowledgment
                                self.file_handler.handle_file_ack(peer_id, message)
                    except json.JSONDecodeError:
                        print(f"Received invalid JSON from peer {peer_id}")
                except socket.timeout:
                    # Send a heartbeat to check if the connection is still alive
                    try:
                        heartbeat = {'type': 'heartbeat'}
                        client_socket.sendall(json.dumps(heartbeat).encode() + b'\n')
                    except:
                        break  # Connection is dead
                except Exception as e:
                    if self.running:
                        print(f"Error receiving data from peer {peer_id}: {e}")
                    break
        finally:
            # Remove peer from our list
            with self.peers_lock:
                if peer_id in self.peers:
                    try:
                        client_socket.close()
                    except:
                        pass
                    del self.peers[peer_id]
                    print(f"Disconnected from peer {peer_id}")
