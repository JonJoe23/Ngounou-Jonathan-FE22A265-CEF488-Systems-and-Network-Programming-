import socket
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext
import logging
import sys
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Server configuration
PORT = 12345
FILE_DIR = 'server_files'

# Thread-safe client storage
clients = {}
clients_lock = threading.Lock()

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TCP Server")
        self.root.geometry("600x400")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Configure CustomTkinter appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Get local IP address
        self.host = self.get_local_ip()

        # Server IP display
        self.ip_frame = ctk.CTkFrame(root)
        self.ip_frame.pack(pady=5, padx=10, fill=tk.X)
        self.ip_label = ctk.CTkLabel(self.ip_frame, text="Server IP:")
        self.ip_label.pack(side=tk.LEFT)
        self.ip_display = ctk.CTkLabel(self.ip_frame, text=self.host, text_color="green")
        self.ip_display.pack(side=tk.LEFT, padx=5)
        self.copy_ip_button = ctk.CTkButton(self.ip_frame, text="Copy IP", command=self.copy_ip, width=80)
        self.copy_ip_button.pack(side=tk.LEFT, padx=5)

        # Start/Stop buttons
        self.button_frame = ctk.CTkFrame(root)
        self.button_frame.pack(pady=5, padx=10, fill=tk.X)
        self.start_button = ctk.CTkButton(self.button_frame, text="Start Server", command=self.start_server)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ctk.CTkButton(self.button_frame, text="Stop Server", command=self.stop_server, fg_color="red", hover_color="darkred")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.configure(state='disabled')

        # Client list display
        self.client_list_label = ctk.CTkLabel(root, text="Connected Clients:")
        self.client_list_label.pack(pady=10)
        self.client_list = tk.Listbox(root, height=5)
        self.client_list.pack(pady=10, padx=10, fill=tk.X)

        # Message log display
        self.message_log = scrolledtext.ScrolledText(root, height=15, state='disabled')
        self.message_log.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Initialize server state
        self.server_socket = None
        self.running = False
        self.accept_thread = None
        os.makedirs(FILE_DIR, exist_ok=True)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"  # Fallback to localhost if unable to get IP

    def copy_ip(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.host)
        self._log_message("Server IP copied to clipboard!")

    def log_message(self, message):
        self.root.after(0, lambda: self._log_message(message))

    def _log_message(self, message):
        self.message_log.configure(state='normal')
        self.message_log.insert(tk.END, message + '\n')
        self.message_log.configure(state='disabled')
        self.message_log.yview(tk.END)
        logger.info(message)

    def update_client_list(self):
        self.root.after(0, self._update_client_list)

    def _update_client_list(self):
        self.client_list.delete(0, tk.END)
        with clients_lock:
            for client_name in clients:
                self.client_list.insert(tk.END, client_name)

    def start_server(self):
        if self.running:
            self.log_message("Server is already running")
            return
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, PORT))
            self.server_socket.listen(5)
            self.running = True
            self.start_button.configure(state='disabled')
            self.stop_button.configure(state='normal')
            self.log_message(f"Server started on {self.host}:{PORT}")
            self.accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
            self.accept_thread.start()
        except Exception as e:
            self.log_message(f"Failed to start server: {e}")
            self.running = False
            self.server_socket = None

    def stop_server(self):
        if not self.running:
            self.log_message("Server is not running")
            return
        self.running = False
        with clients_lock:
            for client_name, client_socket in list(clients.items()):
                try:
                    client_socket.close()
                except:
                    pass
                del clients[client_name]
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
        self.update_client_list()
        self.start_button.configure(state='normal')
        self.stop_button.configure(state='disabled')
        self.log_message("Server stopped")

    def accept_connections(self):
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, addr = self.server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log_message(f"Error accepting connection: {e}")

    def handle_client(self, client_socket, addr):
        client_name = None
        try:
            client_socket.settimeout(1.0)
            client_name = client_socket.recv(1024).decode('utf-8')
            if not client_name:
                return
            with clients_lock:
                if client_name in clients:
                    client_socket.send(json.dumps({"status": "error", "message": "Name already taken"}).encode('utf-8'))
                    return
                clients[client_name] = client_socket
                client_socket.send(json.dumps({"status": "success", "message": "Connected"}).encode('utf-8'))
            self.update_client_list()
            self.log_message(f"Client {client_name} connected from {addr}")

            while self.running:
                try:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                    request = json.loads(data)
                    self.process_request(client_name, client_socket, request)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_message(f"Error with client {client_name}: {e}")
                    break
        except Exception as e:
            self.log_message(f"Error with client {client_name}: {e}")
        finally:
            if client_name:
                with clients_lock:
                    if client_name in clients:
                        del clients[client_name]
                self.update_client_list()
                self.log_message(f"Client {client_name} disconnected")
            client_socket.close()

    def process_request(self, client_name, client_socket, request):
        command = request.get("command")
        if command == "MESSAGE":
            message = request.get("message")
            self.log_message(f"Received from {client_name}: {message}")
            self.broadcast_message(client_name, message)
        elif command == "UPLOAD":
            self.handle_upload(client_name, client_socket, request)
        elif command == "DOWNLOAD":
            self.handle_download(client_name, client_socket, request)
        elif command == "DELETE":
            self.handle_delete(client_name, client_socket, request)
        elif command == "LIST":
            self.handle_list(client_name, client_socket)
        else:
            client_socket.send(json.dumps({"status": "error", "message": "Unknown command"}).encode('utf-8'))

    def broadcast_message(self, sender_name, message):
        with clients_lock:
            for client_name, client_socket in list(clients.items()):
                if client_name != sender_name:
                    try:
                        client_socket.send(json.dumps({"command": "MESSAGE", "sender": sender_name, "message": message}).encode('utf-8'))
                        self.log_message(f"Sent to {client_name}: {sender_name}: {message}")
                    except Exception as e:
                        self.log_message(f"Error sending to {client_name}: {e}")
                        client_socket.close()
                        with clients_lock:
                            if client_name in clients:
                                del clients[client_name]
                        self.update_client_list()

    def handle_upload(self, client_name, client_socket, request):
        filename = request.get("filename")
        file_size = request.get("file_size")
        file_path = os.path.join(FILE_DIR, filename)
        try:
            with open(file_path, 'wb') as f:
                received = 0
                while received < file_size:
                    data = client_socket.recv(1024)
                    if not data:
                        raise Exception("Connection closed during upload")
                    f.write(data)
                    received += len(data)
                if received != file_size:
                    raise Exception(f"Incomplete file received: {received}/{file_size} bytes")
            self.log_message(f"File {filename} uploaded by {client_name}")
            client_socket.send(json.dumps({"status": "success", "message": f"File {filename} uploaded"}).encode('utf-8'))
            self.broadcast_message(client_name, f"Uploaded file {filename}")
        except Exception as e:
            self.log_message(f"Error uploading {filename}: {e}")
            client_socket.send(json.dumps({"status": "error", "message": f"Upload failed: {str(e)}"}).encode('utf-8'))

    def handle_download(self, client_name, client_socket, request):
        filename = request.get("filename")
        file_path = os.path.join(FILE_DIR, filename)
        try:
            if not os.path.exists(file_path):
                client_socket.send(json.dumps({"command": "DOWNLOAD", "status": "error", "message": "File not found"}).encode('utf-8'))
                return
            file_size = os.path.getsize(file_path)
            client_socket.send(json.dumps({"command": "DOWNLOAD", "status": "success", "file_size": file_size, "filename": filename}).encode('utf-8'))
            client_socket.settimeout(5.0)
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    client_socket.send(data)
            self.log_message(f"File {filename} downloaded by {client_name}")
            self.broadcast_message(client_name, f"Downloaded file {filename}")
        except Exception as e:
            self.log_message(f"Error downloading {filename}: {e}")
            client_socket.send(json.dumps({"command": "DOWNLOAD", "status": "error", "message": f"Download failed: {str(e)}"}).encode('utf-8'))

    def handle_delete(self, client_name, client_socket, request):
        filename = request.get("filename")
        file_path = os.path.join(FILE_DIR, filename)
        try:
            if not os.path.exists(file_path):
                client_socket.send(json.dumps({"status": "error", "message": "File not found"}).encode('utf-8'))
                return
            os.remove(file_path)
            self.log_message(f"File {filename} deleted by {client_name}")
            client_socket.send(json.dumps({"status": "success", "message": f"File {filename} deleted"}).encode('utf-8'))
            self.broadcast_message(client_name, f"Deleted file {filename}")
        except Exception as e:
            self.log_message(f"Error deleting {filename}: {e}")
            client_socket.send(json.dumps({"status": "error", "message": f"Delete failed: {str(e)}"}).encode('utf-8'))

    def handle_list(self, client_name, client_socket):
        try:
            files = os.listdir(FILE_DIR)
            client_socket.send(json.dumps({"command": "LIST", "status": "success", "files": files}).encode('utf-8'))
            self.log_message(f"File list requested by {client_name}: {', '.join(files) if files else 'No files'}")
        except Exception as e:
            self.log_message(f"Error listing files: {e}")
            client_socket.send(json.dumps({"command": "LIST", "status": "error", "message": f"List failed: {str(e)}"}).encode('utf-8'))

    def on_closing(self):
        self.stop_server()
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = ctk.CTk()
        app = ServerGUI(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)