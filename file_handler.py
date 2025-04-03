#!/usr/bin/env python3
"""
File handling functionality for the P2P LAN Chat System.
"""

import os
import json
import base64
import hashlib
import time
import socket
import logging



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
        logging.basicConfig(level=logging.DEBUG)


    def send_file(self, peer_id, file_path):
        """
        Send a file to a specific peer.
        
        Args:
            peer_id (str): ID of the peer to send the file to
            file_path (str): Path to the file to send
            
        Returns:
            bool: True if the file transfer was initiated, False otherwise
        """

        try:
            # Validate peer connection
            with self.peer.peers_lock:
                if peer_id not in self.peer.peers:
                    print(f"🔴 Peer {peer_id} not connected")
                    return False


                peer_socket = self.peer.peers[peer_id]['socket']
                peer_nickname = self.peer.peers[peer_id]['nickname']




            if not os.path.exists(file_path):
                print(f"🔴 File not found: {file_path}")
                return False


            
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
        
            # Initiate transfer
            transfer_id = f"{self.peer.peer_id}-{int(time.time())}"
            print(f"📤 Starting transfer {transfer_id} to {peer_nickname}...")
        

            metadata = {
                'type': 'file-metadata',
                'transfer_id': transfer_id,
                'file_name': file_name,
                'file_size': file_size,
                'checksum': self._calculate_checksum(file_path),
                'chunks': (file_size // self.chunk_size) + 1
            }
            try:
                peer_socket.sendall(json.dumps(metadata).encode() + b'\x00')
            except (BrokenPipeError, ConnectionResetError) as e:
                print(f"🔴 Connection lost: {e}")
                self.peer.disconnect_from_peer(peer_id)
                return False

                

            # Enhanced ACK handling
            ack = self._receive_ack(peer_socket, transfer_id)
            if not ack.get('approved', False):
                print(f"🔴 Transfer rejected: {ack.get('reason', 'unknown')}")
                return False

            # File transfer with progress
            with open(file_path, 'rb') as f:
                for seq in range(metadata['chunks']):
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    packet = {
                        'type': 'file-chunk',
                        'transfer_id': transfer_id,
                        'data': base64.b64encode(chunk).decode(),
                        'sequence': seq
                    }
                    try:
                        peer_socket.sendall(json.dumps(packet).encode() + b'\x00')
                    except (ConnectionError, TimeoutError) as e:
                        print(f"🔴 Transfer interrupted: {e}")
                        return False
                    self._update_progress(seq+1, metadata['chunks'])
            
            print(f"\n✅ File {file_name} sent successfully")
            return True

        except Exception as e:
            print(f"🔴 Critical transfer failure: {e}")
            return False


    
    def _receive_ack(self, socket, transfer_id, timeout=10):
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                data = socket.recv(1024)
                if not data:
                    continue
                if b'\x00' in data:
                    msg = json.loads(data.decode().split('\x00', 1)[0])
                    if msg.get('transfer_id') == transfer_id:
                        return msg
            except (socket.timeout, BlockingIOError):
                continue
            except json.JSONDecodeError as e:
                print(f"⚠️ Invalid ACK format: {e}")
                continue
            except ConnectionError as e:
                print(f"⚠️ Connection error during ACK: {e}")
                break
        return {}

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
            return
        transfer = self.active_transfers[transfer_id]

        try:
            data = base64.b64decode(message.get('data', ''))
            transfer['file_handle'].write(data)
            transfer['hash_obj'].update(data)
            transfer['received_size'] += len(data)

            if transfer['received_size'] >= transfer['file_size']:
                transfer['file_handle'].close()
                if transfer['hash_obj'].hexdigest() == message.get('checksum'):
                    print(f"File {transfer['filename']} received successfully")
                else:
                    print("File checksum mismatch")
                del self.active_transfers[transfer_id]

        except Exception as e:
            print(f"File transfer error: {str(e)}")

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
    def _cleanup_transfer(self, transfer_id):
        if transfer_id in self.active_transfers:
            try:
                self.active_transfers[transfer_id]['file_handle'].close()
                os.remove(self.active_transfers[transfer_id]['download_path'])
            except:
                pass
            del self.active_transfers[transfer_id]
    def _calculate_checksum(self, file_path):
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    # Modified progress display
    def _update_progress(self, current, total):
        progress = int(50 * current / total)
        print(f"\r[{'#'*progress}{'-'*(50-progress)}] {current}/{total}", end='', flush=True)
