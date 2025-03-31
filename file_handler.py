#!/usr/bin/env python3
"""
File handling functionality for the P2P LAN Chat System.
"""
import os
import json
import base64
import hashlib
import time

class FileHandler:
    """
    Handles sending and receiving files between peers.
    """
    def __init__(self, peer, chunk_size=8192, download_dir="downloads"):
        """
        Initialize the file handler.
        
        Args:
            peer: Reference to the Peer instance
            chunk_size (int): Size of file chunks in bytes
            download_dir (str): Directory to save downloaded files
        """
        self.peer = peer
        self.chunk_size = chunk_size
        self.download_dir = download_dir
        self.active_transfers = {}  # {transfer_id: {filename, file_size, received_size, file_handle, hash_obj}}
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
    
    def send_file(self, peer_id, file_path):
        """
        Send a file to a specific peer.
        
        Args:
            peer_id (str): ID of the peer to send the file to
            file_path (str): Path to the file to send
            
        Returns:
            bool: True if the file transfer was initiated, False otherwise
        """
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
        
        try:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            with self.peer.peers_lock:
                if peer_id not in self.peer.peers:
                    print(f"Peer {peer_id} not found or not connected")
                    return False
                
                peer_socket = self.peer.peers[peer_id]['socket']
                transfer_id = f"{self.peer.peer_id}_{int(time.time())}_{hash(file_path) % 10000}"
                
                # Send file transfer request
                request = {
                    'type': 'file_request',
                    'transfer_id': transfer_id,
                    'sender_id': self.peer.peer_id,
                    'sender_nickname': self.peer.nickname,
                    'file_name': file_name,
                    'file_size': file_size,
                    'timestamp': time.time()
                }
                peer_socket.sendall(json.dumps(request).encode() + b'\n')
                
                # Send file in chunks
                with open(file_path, 'rb') as file:
                    # Calculate MD5 hash while sending
                    hash_obj = hashlib.md5()
                    
                    sequence = 0
                    while True:
                        chunk = file.read(self.chunk_size)
                        if not chunk:
                            break
                        
                        hash_obj.update(chunk)
                        encoded_chunk = base64.b64encode(chunk).decode('ascii')
                        
                        file_data = {
                            'type': 'file_data',
                            'transfer_id': transfer_id,
                            'sequence': sequence,
                            'data': encoded_chunk,
                            'final': False
                        }
                        
                        peer_socket.sendall(json.dumps(file_data).encode() + b'\n')
                        sequence += 1
                    
                    # Send final chunk with hash
                    final_data = {
                        'type': 'file_data',
                        'transfer_id': transfer_id,
                        'sequence': sequence,
                        'data': '',
                        'final': True,
                        'md5': hash_obj.hexdigest()
                    }
                    peer_socket.sendall(json.dumps(final_data).encode() + b'\n')
                
                print(f"File '{file_name}' sent to {self.peer.peers[peer_id]['nickname']} ({peer_id})")
                return True
                
        except Exception as e:
            print(f"Failed to send file to peer {peer_id}: {e}")
            return False
    
    def handle_file_request(self, sender_id, message):
        """
        Handle a file transfer request.
        
        Args:
            sender_id (str): ID of the peer sending the file
            message (dict): Message containing file information
        """
        transfer_id = message.get('transfer_id')
        sender_nickname = message.get('sender_nickname', 'Unknown')
        file_name = message.get('file_name', 'unknown_file')
        file_size = message.get('file_size', 0)
        
        # Format size for display
        size_str = self._format_size(file_size)
        
        print(f"\n[FILE] {sender_nickname} is sending file '{file_name}' ({size_str})")
        
        # Prepare for receiving the file
        download_path = os.path.join(self.download_dir, file_name)
        
        # If file exists, append a number to avoid overwriting
        counter = 1
        while os.path.exists(download_path):
            name, ext = os.path.splitext(file_name)
            new_name = f"{name}_{counter}{ext}"
            download_path = os.path.join(self.download_dir, new_name)
            counter += 1
        
        try:
            file_handle = open(download_path, 'wb')
            hash_obj = hashlib.md5()
            
            self.active_transfers[transfer_id] = {
                'filename': file_name,
                'file_size': file_size,
                'received_size': 0,
                'file_handle': file_handle,
                'hash_obj': hash_obj,
                'download_path': download_path,
                'sender_id': sender_id
            }
            
            print(f"Receiving file '{file_name}' from {sender_nickname}...")
            
        except Exception as e:
            print(f"Failed to prepare for file reception: {e}")
    
    def handle_file_data(self, sender_id, message):
        """
        Handle received file data.
        
        Args:
            sender_id (str): ID of the peer sending the file
            message (dict): Message containing file data
        """
        transfer_id = message.get('transfer_id')
        
        if transfer_id not in self.active_transfers:
            print(f"Received file data for unknown transfer: {transfer_id}")
            return
        
        transfer = self.active_transfers[transfer_id]
        
        if transfer['sender_id'] != sender_id:
            print(f"Received file data from unexpected sender")
            return
        
        try:
            # If this is the final chunk
            if message.get('final', False):
                # Close the file
                transfer['file_handle'].close()
                
                # Verify the hash
                received_md5 = message.get('md5', '')
                calculated_md5 = transfer['hash_obj'].hexdigest()
                
                if received_md5 and received_md5 == calculated_md5:
                    print(f"\n[FILE] Received file '{transfer['filename']}' successfully")
                    print(f"Saved to: {transfer['download_path']}")
                else:
                    print(f"\n[FILE] Warning: File hash mismatch. File may be corrupted.")
                    print(f"Received: {received_md5}")
                    print(f"Calculated: {calculated_md5}")
                
                # Send acknowledgment
                with self.peer.peers_lock:
                    if sender_id in self.peer.peers:
                        peer_socket = self.peer.peers[sender_id]['socket']
                        ack = {
                            'type': 'file_ack',
                            'transfer_id': transfer_id,
                            'status': 'completed',
                            'message': 'File received successfully'
                        }
                        peer_socket.sendall(json.dumps(ack).encode() + b'\n')
                
                # Remove from active transfers
                del self.active_transfers[transfer_id]
                return
            
            # Process file chunk
            data = message.get('data', '')
            if data:
                decoded_data = base64.b64decode(data)
                transfer['file_handle'].write(decoded_data)
                transfer['hash_obj'].update(decoded_data)
                transfer['received_size'] += len(decoded_data)
                
                # Print progress occasionally
                if transfer['received_size'] % (10 * self.chunk_size) == 0:
                    progress = min(100, int(transfer['received_size'] * 100 / transfer['file_size']))
                    print(f"Receiving file: {progress}% complete")
                
        except Exception as e:
            print(f"Error processing file data: {e}")
            
            # Clean up
            try:
                transfer['file_handle'].close()
            except:
                pass
            
            # Remove from active transfers
            del self.active_transfers[transfer_id]
    
    def handle_file_ack(self, sender_id, message):
        """
        Handle file transfer acknowledgment.
        
        Args:
            sender_id (str): ID of the peer acknowledging the file
            message (dict): Acknowledgment message
        """
        transfer_id = message.get('transfer_id')
        status = message.get('status')
        ack_message = message.get('message', '')
        
        if status == 'completed':
            print(f"File transfer {transfer_id} acknowledged by peer: {ack_message}")
        else:
            print(f"File transfer {transfer_id} failed: {ack_message}")
    
    def _format_size(self, size_bytes):
        """
        Format file size in human-readable form.
        
        Args:
            size_bytes (int): File size in bytes
            
        Returns:
            str: Formatted file size
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f} GB"
