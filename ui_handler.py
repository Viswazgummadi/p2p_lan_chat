#!/usr/bin/env python3
"""
User interface for the P2P LAN Chat System.
"""
import os
import sys
import select
import time
import readline  # Add this import for command history support


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
            '/quit': (self._cmd_quit, 'Exit the application'),
            '/clear': (self._cmd_clear, 'Clear the screen'),
            '/discover': (self._cmd_discover, 'List all discovered peers')
        }

        # Set up readline with history support
        histfile = os.path.join(os.path.expanduser("~"), ".p2pchat_history")
        try:
            readline.read_history_file(histfile)
            # Set history length limit
            readline.set_history_length(1000)
        except FileNotFoundError:
            # Create the file if it doesn't exist
            open(histfile, 'a').close()
        
        # Register to save history on exit
        import atexit
        atexit.register(readline.write_history_file, histfile)


    def _cmd_discover(self, args):
        """Show discovered peers"""
        discovered = self.peer.discovery.get_discovered_peers()
        if not discovered:
            print("\nNo peers discovered yet. Wait for peer discovery broadcasts.")
            return
        print("\nDiscovered peers:")
        for pid, info in discovered.items():
            print(f" {info['nickname']} ({pid[:8]})")
            print(f" Address: {info['ip']}:{info['port']}")
            print(f" Last seen: {time.ctime(info['last_seen'])}\n")



    
    def set_peer(self, peer):
        """
        Set the peer reference.
        
        Args:
            peer: Reference to the Peer instance
        """
        self.peer = peer
    
    def _cmd_clear(self, args):
        """Cross-platform screen clearing"""
        os.system('cls' if os.name == 'nt' else 'clear')


    def process_command(self, user_input):
        if not user_input:
            return

        # Handle normal messages
        if not user_input.startswith('/'):
            self._handle_regular_message(user_input)
            return

        # Split command and arguments
        parts = user_input[1:].split(maxsplit=1)
        command = parts[0].lower()
        args = []
        if len(parts) > 1:
            if command in ['send', 'sendall']:
                subparts = parts[1].split(maxsplit=1)
                args = subparts if len(subparts) > 1 else [subparts[0], '']
            else:
                # Regular argument splitting
                args = parts[1].split()
         # Process the command
        if command == 'help':
            self._cmd_help(args)
        elif command == 'connect':
            self._cmd_connect(args)
        elif command == 'peers':
            self._cmd_peers(args)
        elif command == 'send':
            self._cmd_send(args)
        elif command == 'sendall':
            self._cmd_sendall(args)
        elif command == 'file':
            self._cmd_file(args)
        elif command == 'disconnect':
            self._cmd_disconnect(args)
        elif command == 'quit' or command == 'exit':  # Support both quit and exit
            self._cmd_quit(args)
        elif command == 'clear':
            self._cmd_clear(args)
        elif command == 'discover':
            self._cmd_discover(args)
        else:
            print(f"Unknown command: /{command}")
            print("Type /help for available commands")


    def _handle_regular_message(self, message):
        """Handle a regular chat message (not a command)."""
        if not self.peer.peers:
            print("You are not connected to any peers. Connect with /connect or wait for peers to be discovered.")
        else:
            results = self.peer.send_message_to_all(message)
            success_count = sum(1 for success in results.values() if success)
            if success_count > 0:
                print(f"Message sent to {success_count} peer(s)")


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
                user_input = input("\033[1;32mCHAT>\033[0m ").strip()

                if user_input.strip():
                    self.process_command(user_input)


            except KeyboardInterrupt:
                print("\nUse /quit or /exit to exit properly")
            except Exception as e:
                print(f"Error: {str(e)}")
                

    def _get_non_blocking_input(self):
        """Platform-independent non-blocking input"""
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.readline().strip()
        return None




    def _cmd_help(self, args):
        """Show help for available commands."""
        print("\nAvailable commands:")
        for cmd, (_, desc) in sorted(self.commands.items()):
            print(f"  {cmd:<12} - {desc}")
        print("\nYou can also use '/exit' as an alternative to '/quit'")
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
        else:
            print("\nConnected peers:")
            for pid, info in peers.items():
                print(f"  {info['nickname']} ({pid[:8]}) - {info['ip']}:{info['port']}")

    def _cmd_send(self, args):
        """
        Send a message to a specific peer.
        
        Args:
            args (list): Command arguments [peer_id, message...]
        """
        if len(args) < 2:
            print("Usage: /send <username|peer_id> message")
            return
        
        identifier = args[0]
        message = args[1]

        peer_id = self.peer.find_peer_id(identifier)
        
        if not peer_id:
            print(f"No peer found matching '{identifier}'")
            self._cmd_peers([])
            return

        if self.peer.send_message_to_peer(peer_id, message):
            print(f"Message sent to {self.peer.get_username(peer_id)}")
        else:
            print(f"Failed to send message to peer {identifier}")
    
    def _cmd_sendall(self, args):
        """
        Send a message to all peers.
        
        Args:
            args (list): Command arguments [message...]
        """
        if not args:
            print("Usage: /sendall <message>")
            return
        
        message = args[0]
        results = self.peer.send_message_to_all(message)
        
        success = sum(1 for success in results.values() if success)
        total = len(results)
        print(f"Delivered to {success}/{total} peers")

    
    def _cmd_file(self, args):
        """
        Send a file to a specific peer.
        
        Args:
            args (list): Command arguments [peer_id, filepath]
        """
        if len(args) < 2:
            print("Usage: /file <peer> <filepath>\n"
                  "Example: /file alice ~/documents/report.pdf")
            return
        
        peer_id = self.peer.find_peer_id(args[0])
        if not peer_id:
            print(f"🔴 Peer '{args[0]}' not found. Available peers:")
            self._cmd_peers([])
            return
            
        file_path = os.path.expanduser(' '.join(args[1:]))
        if not os.path.exists(file_path):
            print(f"🔴 File not found: {file_path}")
            return
        print(f"📤 Initiating file transfer to {args[0]}...")
        if self.peer.send_file_to_peer(peer_id, file_path):
            print("🔄 Transfer in progress...")
        else:
            print("🔴 Failed to start transfer")

    
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
    
    # In UIHandler class
    def _cmd_quit(self, args):
        """Proper shutdown sequence"""
        print("Exiting application...")
        if self.peer:
            try:
                self.peer.stop()
            except Exception as e:
                print(f"Error stopping peer: {e}")
        # Force immediate exit
        sys.stdout.flush()  # Flush stdout to ensure all messages are displayed
        os._exit(0)  # Force exit all threads
