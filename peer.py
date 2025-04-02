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
        
        # Add blocklist and connection tracking
        self.blocklist = set()  # {(ip, port)}
        self.connection_attempts = {}  # {(ip, port): attempt_count}

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
        
        # Signal discovery to stop
        self.discovery.running = False

        # Close all sockets
        with self.peers_lock:
            for peer_id  in list(self.peers.keys()):
                try:
                    self.peers[peer_id]['socket'].shutdown(socket.SHUT_RDWR)
                    self.peers[peer_id]['socket'].close()
                except Exception as e:
                    pass
                del self.peers[peer_id]
        # Join threads
        for t in self.threads:
            t.join(timeout=1)


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
                self.server_socket.shutdown(socket.SHUT_RDWR)
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
        # Add to blocklist check
        if (ip, port) in self.blocklist:
            print(f"Blocked connection to {ip}:{port} ")
            return False

        try:

            # Create socket and connect
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, port))
            

            # Send our information
            handshake_data = {
                'type': 'handshake',
                'peer_id': self.peer_id,
                'nickname': self.nickname,
                'ip': self.ip,
                'port': self.port,
            }

            client_socket.sendall(json.dumps(handshake_data).encode() + b'\x00')
            response = client_socket.recv(1024).decode()
            peer_info = json.loads(response.split('\x00')[0])

            # Finalize connection
            with self.peers_lock:
                self.peers[peer_info['peer_id']] = {
                    'socket': client_socket,
                    'ip': ip,
                    'port': port,
                    'nickname': peer_info.get('nickname', 'Unknown'),
                }



            print(f"Connected to {peer_info['nickname']} at {ip}:{port}")
            # Start a thread to handle messages from this peer
            # This is critical for bidirectional communication
            handler_thread = threading.Thread(
                target=self._handle_peer,
                args=(peer_info['peer_id'], client_socket)
            )
            handler_thread.daemon = True
            handler_thread.start()
            self.threads.append(handler_thread)

            return True
        except Exception as e:
            print(f"🔴 Connection failed: at {ip}:{port} : {str(e)}")
            return False

    
    def disconnect_from_peer(self, identifier):
        """
        Disconnect from a specific peer.
        
        Args:
            peer_id (str): ID of the peer to disconnect from
        """

        peer_id = self.find_peer_id(identifier)


        if not peer_id:
            print(f"Peer '{identifier}' not found")
            return



        with self.peers_lock:
            if peer_id in self.peers:


                peer_info = self.peers[peer_id]
                # Close socket and cleanup
                try:

                    # Send formal disconnect notice
                    disconnect_msg = {
                        'type': 'disconnect',
                        'peer_id': self.peer_id,
                        'reason': 'user-requested'
                    }
                    peer_info['socket'].sendall(json.dumps(disconnect_msg).encode() + b'\x00')


                    # Close connection
                    peer_info['socket'].shutdown(socket.SHUT_RDWR)
                    peer_info['socket'].close()
                
                    # Add to blocklist
                    self.blocklist.add((peer_info['ip'], peer_info['port']))
                
                    del self.peers[peer_id]

                    print(f"🔌 Disconnected from {peer_info['nickname']} ({peer_id[:8]})")
                except Exception as e:
                    print(f"⚠️ Error disconnecting: {str(e)}")
                    # Still remove from peers dict even if there was an error
                    if peer_id in self.peers:
                        del self.peers[peer_id]

    
    def get_peers(self):
        """Get a list of connected peers."""
        with self.peers_lock:
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
        """Get the username for a peer ID."""
        with self.peers_lock:
            if peer_id in self.peers:
                return self.peers[peer_id].get('nickname', 'Unknown')
            return 'Unknown'


    def find_peer_id(self, identifier):
        """Find peer by username or partial ID"""
        with self.peers_lock:
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
            peer_data = b''

            while True:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                peer_data += chunk
                if b'\x00' in peer_data:  # Match client delimiter
                    break
            if not peer_data:
                client_socket.close()
                return

            peer_info = json.loads(peer_data.decode().split('\x00')[0])
            peer_id = peer_info.get('peer_id')  # Extract peer_id from peer_info

            # Check if peer_id is valid
            # Validate peer information
            if not peer_id or peer_id == self.peer_id:
                client_socket.close()
                return

            with self.peers_lock:
                if peer_id in self.peers:
                    # Already connected
                    client_socket.close()
                    return

            # Send our information
            handshake_response = {
                'type': 'handshake',
                'peer_id': self.peer_id,
                'nickname': self.nickname,
                'ip': self.ip,
                'port': self.port
            }
            client_socket.sendall(json.dumps(handshake_response).encode() + b'\x00')
                    
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
        client_socket.settimeout(30)  # 60 second timeout
        
        try:
            buffer = b''
            while self.running:
                try:
                    # Receive data
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        print(f"Connection closed by peer {peer_id}")
                        break
                
                    buffer += chunk
                
                    # Process complete messages
                    while b'\x00' in buffer:
                        msg_data, buffer = buffer.split(b'\x00', 1)
                        if msg_data:
                            try:
                                message = json.loads(msg_data.decode())
                                message_type = message.get('type')
                            
                                if message_type == 'text':
                                    self.message_handler.handle_message(peer_id, message)

                                elif message_type == 'file-metadata':
                                    self.file_handler.handle_file_request(peer_id, message)
                                elif message_type == 'file-chunk':
                                    self.file_handler.handle_file_data(peer_id, message)
                                elif message_type == 'file-ack':
                                    self.file_handler.handle_file_ack(peer_id, message)
                                
                                elif message_type == 'disconnect':
                                    print(f"Peer {peer_id} has disconnected")
                                    return
                                elif message_type == 'heartbeat':
                                # Just acknowledge heartbeats
                                    continue
                            
                                else:
                                    print(f"Unknown message type: {message_type}")

                            except json.JSONDecodeError:
                                print(f"Received invalid JSON from peer {peer_id}")
                
                except socket.timeout:
                    # Send heartbeat
                    try:
                        heartbeat = {'type': 'heartbeat'}
                        client_socket.sendall(json.dumps(heartbeat).encode() + b'\x00')
                    except Exception as e:
                        print(f"Error sending heartbeat: {e}")
                        break
                except Exception as e:
                    print(f"Error receiving data from peer {peer_id}: {e}")
                    break
        finally:
            # Clean up
            with self.peers_lock:
                if peer_id in self.peers:
                    try:
                        client_socket.close()
                    except Exception as e:
                        print(f"Error closing connection: {e}")
                    del self.peers[peer_id]
                    print(f"Disconnected from peer {peer_id}")

