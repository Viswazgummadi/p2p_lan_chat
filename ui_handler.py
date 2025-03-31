#!/usr/bin/env python3
"""
User interface for the P2P LAN Chat System.
"""
import os
import sys

class UIHandler:
    """
    Handles user interface and commands for the P2P chat application.
    """
    def __init__(self):
        """Initialize the UI handler."""
        self.peer = None
        self.commands = {
            '/help': (self._cmd_help, 'Show available commands'),
            '/connect': (self._cmd_connect, 'Connect to a peer: /connect <ip> <port>'),
            '/peers': (self._cmd_peers, 'List connected peers'),
            '/send': (self._cmd_send, 'Send message to specific peer: /send <peer_id> <message>'),
            '/sendall': (self._cmd_sendall, 'Send message to all peers: /sendall <message>'),
            '/file': (self._cmd_file, 'Send file to specific peer: /file <peer_id> <filepath>'),
            '/disconnect': (self._cmd_disconnect, 'Disconnect from a peer: /disconnect <peer_id>'),
            '/quit': (self._cmd_quit, 'Exit the application')
        }
    
    def set_peer(self, peer):
        """
        Set the peer reference.
        
        Args:
            peer: Reference to the Peer instance
        """
        self.peer = peer
    
    def print_welcome_message(self):
        """Print welcome message and basic instructions."""
        print("\n" + "="*60)
        print("Welcome to P2P LAN Chat System with File Sharing")
        print("="*60)
        print("Type /help to see available commands")
        print("Your messages will be shared with all connected peers")
        print("="*60 + "\n")
    
    def get_user_input(self, prompt=""):
        """
        Get input from the user.
        
        Args:
            prompt (str): Prompt to display
            
        Returns:
            str: User input
        """
        try:
            return input(prompt)
        except EOFError:
            return ""
    
    def command_loop(self):
        """Main command loop for processing user input."""
        while True:
            try:
                user_input = self.get_user_input("> ")
                if not user_input:
                    continue
                
                # Check if this is a command
                if user_input.startswith('/'):
                    # Parse the command
                    parts = user_input.split()
                    command = parts[0].lower()
                    args = parts[1:]
                    
                    if command in self.commands:
                        # Execute the command
                        self.commands[command][0](args)
                    else:
                        print(f"Unknown command: {command}")
                        print("Type /help to see available commands")
                else:
                    # Send message to all peers
                    if not self.peer.peers:
                        print("You are not connected to any peers. Connect with /connect or wait for peers to be discovered.")
                    else:
                        results = self.peer.send_message_to_all(user_input)
                        success_count = sum(1 for success in results.values() if success)
                        if success_count > 0:
                            print(f"Message sent to {success_count} peer(s)")
            except KeyboardInterrupt:
                # Handle Ctrl+C
                print("\nUse /quit to exit")
            except Exception as e:
                print(f"Error: {e}")
    
    def _cmd_help(self, args):
        """Show help for available commands."""
        print("\nAvailable commands:")
        for cmd, (_, desc) in sorted(self.commands.items()):
            print(f"  {cmd:<12} - {desc}")
        print()
    
    def _cmd_connect(self, args):
        """
        Connect to a peer.
        
        Args:
            args (list): Command arguments [ip, port]
        """
        if len(args) != 2:
            print("Usage: /connect <ip> <port>")
            return
        
        try:
            ip = args[0]
            port = int(args[1])
            
            print(f"Connecting to {ip}:{port}...")
            if self.peer.connect_to_peer(ip, port):
                print(f"Successfully connected to peer at {ip}:{port}")
            else:
                print(f"Failed to connect to peer at {ip}:{port}")
        except ValueError:
            print("Port must be a number")
        except Exception as e:
            print(f"Error connecting to peer: {e}")
    
    def _cmd_peers(self, args):
        """List connected peers."""
        peers = self.peer.get_peers()
        if not peers:
            print("No peers connected")
            return
        
        print("\nConnected peers:")
        for peer_id, info in peers.items():
            print(f"  {info['nickname']} ({peer_id})")
            print(f"    IP: {info['ip']}:{info['port']}")
        print()
    
    def _cmd_send(self, args):
        """
        Send a message to a specific peer.
        
        Args:
            args (list): Command arguments [peer_id, message...]
        """
        if len(args) < 2:
            print("Usage: /send <peer_id> <message>")
            return
        
        peer_id = args[0]
        message = ' '.join(args[1:])
        
        if self.peer.send_message_to_peer(peer_id, message):
            print(f"Message sent to peer {peer_id}")
        else:
            print(f"Failed to send message to peer {peer_id}")
    
    def _cmd_sendall(self, args):
        """
        Send a message to all peers.
        
        Args:
            args (list): Command arguments [message...]
        """
        if not args:
            print("Usage: /sendall <message>")
            return
        
        message = ' '.join(args)
        results = self.peer.send_message_to_all(message)
        
        success_count = sum(1 for success in results.values() if success)
        if success_count > 0:
            print(f"Message sent to {success_count} peer(s)")
        else:
            print("Failed to send message to any peers")
    
    def _cmd_file(self, args):
        """
        Send a file to a specific peer.
        
        Args:
            args (list): Command arguments [peer_id, filepath]
        """
        if len(args) < 2:
            print("Usage: /file <peer_id> <filepath>")
            return
        
        peer_id = args[0]
        file_path = ' '.join(args[1:])
        
        # Expand ~ in file path
        file_path = os.path.expanduser(file_path)
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return
        
        print(f"Sending file {file_path} to peer {peer_id}...")
        if self.peer.send_file_to_peer(peer_id, file_path):
            print(f"File transfer initiated to peer {peer_id}")
        else:
            print(f"Failed to initiate file transfer to peer {peer_id}")
    
    def _cmd_disconnect(self, args):
        """
        Disconnect from a peer.
        
        Args:
            args (list): Command arguments [peer_id]
        """
        if len(args) != 1:
            print("Usage: /disconnect <peer_id>")
            return
        
        peer_id = args[0]
        self.peer.disconnect_from_peer(peer_id)
    
    def _cmd_quit(self, args):
        """Exit the application."""
        print("Exiting application...")
        if self.peer:
            self.peer.stop()
        sys.exit(0)
