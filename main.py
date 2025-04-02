#!/usr/bin/env python3
"""
Main entry point for the P2P LAN Chat System with File Sharing.
"""
import sys
import argparse
from peer import Peer
from ui_handler import UIHandler
import time
def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='P2P LAN Chat System with File Sharing')
    parser.add_argument('--port', type=int, default=0,
                        help='Port to listen on (default: random available port)')
    parser.add_argument('--nickname', type=str, default=None,
                        help='Your nickname in the chat (default: generated)')
    return parser.parse_args()

def main():
    """Main function to run the P2P chat application."""
    args = parse_arguments()
    
    # Create UI Handler
    ui = UIHandler()
    ui.print_welcome_message()
    
    # Get nickname if not provided
    nickname = args.nickname or ui.get_user_input("Enter your nickname: ") or "Anonymous"

    
    # Create and start peer
    try:
        peer = Peer(nickname=nickname, port=args.port)
        peer.start()
        ui.set_peer(peer)
        
        # Main command loop
        ui.command_loop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'peer' in locals():
            peer.stop()
    
    print("Application terminated.")
    sys.exit(0)

if __name__ == "__main__":
    main()
