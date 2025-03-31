# P2P LAN Chat System with File Sharing

A Python-based peer-to-peer chat system that enables real-time messaging and file sharing over a local area network without requiring a central server.

## Features
- Real-time messaging between peers
- File sharing capabilities
- Peer discovery on local network
- Decentralized architecture
- Simple command-line interface

## Requirements
- Python 3.6+
- Network connection (LAN)

## Installation
1. Clone the repository
2. Ensure Python 3.6+ is installed
3. No additional packages required (uses standard library)

## Usage
1. Run `python main.py` to start the application
2. Follow the on-screen instructions to connect with peers
3. Use commands like `/connect`, `/send`, `/file`, and `/quit`

## Commands
- `/help` - Show available commands
- `/connect <ip> <port>` - Connect to a peer
- `/peers` - List connected peers
- `/send <peer_id> <message>` - Send message to specific peer
- `/sendall <message>` - Send message to all connected peers
- `/file <peer_id> <filepath>` - Send file to specific peer
- `/quit` - Exit the application
