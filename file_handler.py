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
            # Normalize file path
            file_path = os.path.expanduser(file_path)
            
            
            with self.peer.peers_lock:
                if peer_id not in self.peer.peers:
                    print(f"🔴 Peer {peer_id} not connected")
                    return False


                peer_socket = self.peer.peers[peer_id]['socket']
                peer_nickname = self.peer.peers[peer_id]['nickname']




            if not os.path.exists(file_path):
                print(f"🔴 File not found: {file_path}")
                return False

            
            if not os.path.isfile(file_path):
                print(f"🔴 Not a file: {file_path}")
                return False
                
            try:
                with open(file_path, 'rb') as test_read:
                    test_read.read(1)
            except Exception as e:
                print(f"🔴 Cannot read file: {e}")
                return False
            
            
            
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
        
            
            # Calculate checksum before transfer
            try:
                checksum = self._calculate_checksum(file_path)
            except Exception as e:
                print(f"🔴 Failed to calculate checksum: {e}")
                return False
            
            
            
            # Initiate transfer
            transfer_id = f"{self.peer.peer_id}-{int(time.time())}"
            print(f"📤 Starting transfer {transfer_id} to {peer_nickname}...")
        

            metadata = {
                'type': 'file-metadata',
                'transfer_id': transfer_id,
                'file_name': file_name,
                'file_size': file_size,
                'checksum': checksum,
                'sender_nickname': self.peer.nickname,
                'chunks': (file_size // self.chunk_size) + (1 if file_size % self.chunk_size else 0)
            }
            try:
                peer_socket.sendall(json.dumps(metadata).encode() + b'\x00')
            except Exception as e:
                print(f"🔴 Connection error while sending metadata: {e}")
                self.peer.disconnect_from_peer(peer_id)
                return False

                

            # Enhanced ACK handling
            ack = self._receive_ack(peer_socket, transfer_id)

            if not ack:
                print(f"🔴 No acknowledgment received for transfer {transfer_id}")
                return False
                
            if not ack.get('approved', False):
                print(f"🔴 Transfer rejected: {ack.get('reason', 'unknown')}")
                return False
        
        # Transfer file in chunks
            chunks_sent = 0
            total_chunks = metadata['chunks']




            
            try:
                with open(file_path, 'rb') as f:
                    for seq in range(total_chunks):
                        chunk = f.read(self.chunk_size)
                        if not chunk:  # End of file
                            break
                        
                        # Create chunk packet
                        packet = {
                            'type': 'file-chunk',
                            'transfer_id': transfer_id,
                            'data': base64.b64encode(chunk).decode(),
                            'sequence': seq
                        }
                        
                        # Add final file checksum to the last chunk
                        if seq == total_chunks - 1 or not chunk:
                            packet['final'] = True
                            packet['file_checksum'] = checksum
                        
                        # Send chunk
                        try:
                            peer_socket.sendall(json.dumps(packet).encode() + b'\x00')
                            chunks_sent += 1
                            self._update_progress(chunks_sent, total_chunks)
                        except Exception as e:
                            print(f"\n🔴 Error sending chunk {seq}: {e}")
                            return False
                        
                        # Small delay to prevent overwhelming the receiver
                        time.sleep(0.001)
            
            except Exception as e:
                print(f"\n🔴 Error reading file: {e}")
                return False
            
            print(f"\n✅ All chunks sent for {file_name}")
            return True
            
        except Exception as e:
            print(f"🔴 Critical transfer failure: {e}")
            # Add stack trace for debugging
            import traceback
            traceback.print_exc()
            return False


    
    def _receive_ack(self, socket_obj, transfer_id, timeout=10):
            # Save original timeout
        original_timeout = socket_obj.gettimeout()
        try:
            # Set a new timeout for this operation
            socket_obj.settimeout(1.0)  # Short timeout for responsive checks
            
            end_time = time.time() + timeout
            
            while time.time() < end_time:
                try:
                    data = socket_obj.recv(1024)
                    if not data:
                        time.sleep(0.1)  # Small sleep to prevent CPU spinning
                        continue
                        
                    if b'\x00' in data:
                        msg_data = data.decode().split('\x00', 1)[0]
                        msg = json.loads(msg_data)
                        if msg.get('transfer_id') == transfer_id:
                            return msg
                except socket.timeout:
                    # Socket timeout is expected, just continue
                    continue
                except BlockingIOError:
                    # Non-blocking socket not ready
                    continue
                except ConnectionError as e:
                    # Connection issues
                    print(f"⚠️ Connection error while waiting for acknowledgment: {e}")
                    break
                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid data format: {e}")
                    continue
                except Exception as e:
                    print(f"⚠️ Unexpected error during ACK: {type(e).__name__}: {e}")
                    break
                    
            # If we get here, we've timed out
            print(f"⏱️ Timed out waiting for acknowledgment")
            return {}
            
        finally:
            # Restore original timeout
            try:
                socket_obj.settimeout(original_timeout)
            except:
                pass  # Ignore errors when restoring timeout

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
        
        print(f"\n[FILE] {sender_nickname} is sending file '{file_name}' ({self._format_size(file_size)})")

        try:
            final_dir = os.path.abspath(self.download_dir)
            temp_filename = f".{transfer_id}.{file_name}.part"
            temp_path = os.path.join(final_dir, temp_filename)
            final_path = os.path.join(final_dir, file_name)

            # Ensure directory exists
            os.makedirs(final_dir, exist_ok=True)

            # Check for existing files and find available name
            counter = 1
            base_name, ext = os.path.splitext(file_name)
            while os.path.exists(final_path):
                final_path = os.path.join(final_dir, f"{base_name}_{counter}{ext}")
                counter += 1

            # Create temporary file
            temp_file = open(temp_path, 'wb')
            hash_obj = hashlib.md5()

            self.active_transfers[transfer_id] = {
                'temp_path': temp_path,
                'final_path': final_path,
                'file_size': file_size,
                'received_size': 0,
                'file_handle': temp_file,
                'hash_obj': hash_obj,
                'sender_id': sender_id,
                'expected_checksum': message.get('checksum')
            }

            # Send acknowledgment
            ack_message = {
                'type': 'file-ack',
                'transfer_id': transfer_id,
                'approved': True,
                'message': f"Ready to receive {file_name}"
            }
            self._send_to_peer(sender_id, ack_message)
            print(f"Receiving file '{file_name}' from {sender_nickname}...")

        except Exception as e:
            print(f"Failed to prepare for file reception: {e}")
            self._cleanup_transfer(transfer_id)
            reject_message = {
                'type': 'file-ack',
                'transfer_id': transfer_id,
                'approved': False,
                'reason': str(e)
            }
            self._send_to_peer(sender_id, reject_message)
            

    def handle_file_data(self, sender_id, message):
        """
        Handle received file data with atomic file operations.
        """
        transfer_id = message.get('transfer_id')
        if transfer_id not in self.active_transfers:
            print(f"Ignoring chunk for unknown transfer: {transfer_id}")
            return

        transfer = self.active_transfers[transfer_id]
        
        try:
            data = base64.b64decode(message.get('data', ''))
            transfer['file_handle'].write(data)
            transfer['hash_obj'].update(data)
            transfer['received_size'] += len(data)

            # Check for transfer completion
            if transfer['received_size'] >= transfer['file_size']:
                transfer['file_handle'].close()
                calculated_checksum = transfer['hash_obj'].hexdigest()
                expected_checksum = transfer.get('expected_checksum')

                # Validate checksum before finalizing
                if calculated_checksum == expected_checksum:
                    # Atomic rename from temp to final path
                    os.rename(transfer['temp_path'], transfer['final_path'])
                    print(f"✅ File {os.path.basename(transfer['final_path'])} received successfully")
                else:
                    print(f"⚠️ Checksum mismatch for {transfer['final_path']}")
                    raise ValueError("Checksum verification failed")

                # Send success notification
                ack_message = {
                    'type': 'file-complete',
                    'transfer_id': transfer_id,
                    'success': True,
                    'checksum_match': True
                }
                self._send_to_peer(sender_id, ack_message)
                del self.active_transfers[transfer_id]

        except Exception as e:
            print(f"File transfer error: {str(e)}")
            self._cleanup_transfer(transfer_id)
            error_message = {
                'type': 'file-error',
                'transfer_id': transfer_id,
                'error': str(e)
            }
            self._send_to_peer(sender_id, error_message)

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
        """
        Enhanced cleanup with proper temporary file handling.
        """
        if transfer_id in self.active_transfers:
            transfer = self.active_transfers[transfer_id]
            try:
                # Close file handle if open
                if transfer['file_handle'] and not transfer['file_handle'].closed:
                    transfer['file_handle'].close()
                
                # Remove temporary file
                if os.path.exists(transfer['temp_path']):
                    os.remove(transfer['temp_path'])
                    
                # Remove any empty final path that might have been created
                if os.path.exists(transfer['final_path']) and os.path.getsize(transfer['final_path']) == 0:
                    os.remove(transfer['final_path'])
            except Exception as e:
                print(f"Cleanup error: {str(e)}")
            finally:
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


    def _send_to_peer(self, peer_id, message):
        """Utility method for safe message sending."""
        with self.peer.peers_lock:
            if peer_id in self.peer.peers:
                try:
                    self.peer.peers[peer_id]['socket'].sendall(
                        json.dumps(message).encode() + b'\x00'
                    )
                    return True
                except Exception as e:
                    print(f"Failed to send message to {peer_id}: {str(e)}")
                    return False
            return False
