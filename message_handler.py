#!/usr/bin/env python3
"""
Message handling functionality for the P2P LAN Chat System.
"""
import json
import time

class MessageHandler:
    """
    Handles sending and receiving text messages between peers.
    """
    def __init__(self, peer):
        """
        Initialize the message handler.
        
        Args:
            peer: Reference to the Peer instance
        """
        self.peer = peer
    
    def send_message(self, peer_id, message_content):
        """
        Send a text message to a specific peer.
        
        Args:
            peer_id (str): ID of the peer to send the message to
            message_content (str): Content of the message
            
        Returns:
            bool: True if the message was sent, False otherwise
        """
        with self.peer.peers_lock:
            if peer_id not in self.peer.peers:
                print(f"Peer {peer_id} not found or not connected")
                return False
            
            peer_socket = self.peer.peers[peer_id]['socket']
            try:
                message = {
                    'type': 'text',
                    'sender_id': self.peer.peer_id,
                    'sender_nickname': self.peer.nickname,
                    'content': message_content,
                    'timestamp': time.time()
                }
                peer_socket.sendall(json.dumps(message).encode() + b'\x00')
                return True
            except Exception as e:
                print(f"Failed to send message to peer {peer_id}: {e}")
                # Close the connection as it may be broken
                try:
                    peer_socket.close()
                except:
                    pass
                del self.peer.peers[peer_id]
                return False
    
    def send_message_to_all(self, message_content):
        """
        Send a text message to all connected peers.
        
        Args:
            message_content (str): Content of the message
            
        Returns:
            dict: Dictionary mapping peer_id to success status
        """
        results = {}
        with self.peer.peers_lock:
            current_peers = list(self.peer.peers.items())
        for peer_id,peer_info in current_peers:
            try:
                success = self.send_message(peer_id, message_content)
                results[peer_id] = success
                if not success:
                    print(f"Failed to send to {peer_info['nickname']}")
            except Exception as e:
                print(f"Failed to send to {peer_info['nickname']}: {str(e)}")
        return results
    
    def handle_message(self, sender_id, message):
        """
        Handle a received text message.
        
        Args:
            sender_id (str): ID of the peer who sent the message
            message (dict): Message data
        """
        if message.get('type') != 'text':
            return
        
        sender_nickname = message.get('sender_nickname', 'Unknown')
        content = message.get('content', '')
        timestamp = message.get('timestamp', time.time())
        
        # Format timestamp
        time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
        

        # Print the message with a carriage return to overwrite any prompt
        print(f"\n\033[2K\r[{time_str}] {message['sender_nickname']}: {content}")
        print("CHAT> ", end='', flush=True)  # Reprint the prompt


