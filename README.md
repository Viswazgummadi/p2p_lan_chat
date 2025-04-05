# P2P LAN Chat System with File Sharing

A lightweight, decentralized peer-to-peer chat application for local area networks with integrated file sharing capabilities. This application allows users to discover peers, exchange messages, and transfer files without requiring a central server.

---

## Features

- **Decentralized Architecture**: No central server required - fully P2P communication.  
- **Automatic Peer Discovery**: Automatically finds other peers on the local network.  
- **Direct Messaging**: Send messages to specific peers by nickname or ID.  
- **Broadcast Messaging**: Send messages to all connected peers simultaneously.  
- **File Sharing**: Transfer files to other peers with integrity verification.  
- **Command-Line Interface**: Simple and intuitive command-based interface.  
- **Chat History**: Maintains command history between sessions.  
- **Secure Communication**: Uses checksums to verify file integrity.  

---

## Requirements

- Python 3.6 or higher  
- No external dependencies (uses Python's standard library)  
- Compatible with Windows, macOS, and Linux  

---

## Installation

```bash
# Clone this repository
git clone https://github.com/yourusername/p2p-lan-chat.git
cd p2p-lan-chat

# Make the main script executable (for Unix-based systems)
chmod +x main.py
```

No additional installation steps are required.

---

## Usage

### Starting the Application

Run the application using Python:

```bash
python main.py --nickname <your_nickname> --port <port_number>
```

Options:
- `--nickname`: Set your display name (defaults to "Anonymous")  
- `--port`: Specify the TCP port to listen on (defaults to a random available port)  

---

### Command Reference

| Command          | Description                              | Example                                 |
|------------------|------------------------------------------|-----------------------------------------|
| `/help`          | Show available commands                  | `/help`                                 |
| `/connect`       | Connect to a peer by IP and port         | `/connect 192.168.1.5 8000`             |
| `/peers`         | List all connected peers                 | `/peers`                                |
| `/send`          | Send a message to a specific peer        | `/send Bob Hello there!`                |
| `/sendall`       | Send a message to all connected peers    | `/sendall Meeting in 5 minutes`         |
| `/file`          | Send a file to a specific peer           | `/file Alice ~/Documents/report.pdf`    |
| `/disconnect`    | Disconnect from a specific peer          | `/disconnect Bob`                       |
| `/discover`      | Discover peers on the local network      | `/discover`                             |
| `/clear`         | Clear the console screen                 | `/clear`                                |
| `/quit`, `/exit` | Exit the application                     | `/quit`, `/exit`                        |

---

### Sending Messages

To send a message:

#### 1. To all connected peers:

```bash
CHAT> Hello everyone!
```

#### 2. To a specific peer:

```bash
CHAT> /send Bob How are you?
```

---

### File Transfers

To send a file:

```bash
CHAT> /file Bob ~/Documents/example.pdf
```

The file will be sent in chunks and saved in the recipient's `downloads/` folder.

---

### Managing Connections

#### 1. Connect to a peer:

```bash
CHAT> /connect 192.168.1.10 8000
```

#### 2. Disconnect from a peer:

```bash
CHAT> /disconnect Alice
```

#### 3. Discover peers on the network:

```bash
CHAT> /discover
```

---

## Architecture

The application consists of the following components:

- **`peer.py`**: Manages connections, handles incoming/outgoing messages, and coordinates other modules  
- **`message_handler.py`**: Sends and receives text messages between peers  
- **`file_handler.py`**: Manages file transfers with chunking and checksum validation  
- **`discovery.py`**: Handles automatic peer discovery via UDP broadcasts  
- **`ui_handler.py`**: Provides an interactive command-line interface for users  
- **`utils.py`**: Contains utility functions for IP detection, port management, etc  

---

## Configuration

You can modify default settings by editing the source code:

- **Discovery Port**: Change `discovery_port` in `discovery.py`  
- **Download Directory**: Modify `download_dir` in `file_handler.py`  
- **Chunk Size for File Transfers**: Adjust `chunk_size` in `file_handler.py`  

---

## Development Guide

### Project Structure

```plaintext
p2p-lan-chat/
├── main.py             # Entry point for the application
├── peer.py             # Core peer management functionality
├── message_handler.py  # Handles text messaging between peers
├── file_handler.py     # Manages file transfers
├── discovery.py        # Peer discovery service using UDP broadcasts
├── ui_handler.py       # Command-line interface for user interaction
└── utils.py            # Utility functions (IP detection, port management)
```

### Adding New Features

1. Add new commands in `UIHandler`  
2. Implement new message types in `MessageHandler`  
3. Extend functionality by creating new modules or modifying existing ones  

**Example: Adding encryption support**

```text
1. Create an encryption module (encryption.py) using libraries like cryptography  
2. Integrate encryption into MessageHandler and FileHandler  
```

---

## Troubleshooting

### Common Issues

1. **Peer Discovery Fails**  
    - Ensure all devices are on the same local network  
    - Check if UDP port `35000` is open on your firewall  

2. **Connection Issues**  
    - Verify that the target peer is running and accessible  
    - Check if TCP ports are blocked by firewalls  

3. **File Transfer Fails**  
    - Ensure sufficient disk space is available  
    - Check if you have write permissions in the download directory  

### Debugging Tips

Use tools like **Wireshark** or **tcpdump** to monitor network traffic on ports used by the application:

```bash
tcpdump -i eth0 port 35000 or portrange 8000-9000
```

---

## License

This project is licensed under the **MIT License**.

---

_Last updated: April 5, 2025_
