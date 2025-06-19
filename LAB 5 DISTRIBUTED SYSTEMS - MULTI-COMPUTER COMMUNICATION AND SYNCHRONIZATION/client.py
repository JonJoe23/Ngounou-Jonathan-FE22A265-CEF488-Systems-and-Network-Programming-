import socket
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext, filedialog
import logging
import sys
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Client configuration
DEFAULT_HOST = '127.0.0.1'
PORT = 12345

class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Client")
        self.root.geometry("600x500")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Configure CustomTkinter appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Connection frame
        self.conn_frame = ctk.CTkFrame(root)
        self.conn_frame.pack(pady=10, padx=10, fill=tk.X)
        self.ip_label = ctk.CTkLabel(self.conn_frame, text="Server IP:")
        self.ip_label.pack(side=tk.LEFT)
        self.ip_entry = ctk.CTkEntry(self.conn_frame, placeholder_text="Enter server IP")
        self.ip_entry.insert(0, DEFAULT_HOST)
        self.ip_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.name_label = ctk.CTkLabel(self.conn_frame, text="Name:")
        self.name_label.pack(side=tk.LEFT)
        self.name_entry = ctk.CTkEntry(self.conn_frame, placeholder_text="Your name")
        self.name_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.connect_button = ctk.CTkButton(self.conn_frame, text="Connect", command=self.start_connect_thread)
        self.connect_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_button = ctk.CTkButton(self.conn_frame, text="Disconnect", command=self.disconnect, fg_color="red", hover_color="darkred")
        self.disconnect_button.pack(side=tk.LEFT, padx=5)
        self.disconnect_button.configure(state='disabled')

        # Message display
        self.message_log = scrolledtext.ScrolledText(root, height=15, state='disabled')
        self.message_log.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Message input
        self.message_frame = ctk.CTkFrame(root)
        self.message_frame.pack(pady=5, padx=10, fill=tk.X)
        self.message_entry = ctk.CTkEntry(self.message_frame, placeholder_text="Enter message or filename for download/delete")
        self.message_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.send_button = ctk.CTkButton(self.message_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT)

        # File operation buttons
        self.file_frame = ctk.CTkFrame(root)
        self.file_frame.pack(pady=5, padx=10, fill=tk.X)
        self.upload_button = ctk.CTkButton(self.file_frame, text="Upload File", command=self.upload_file)
        self.upload_button.pack(side=tk.LEFT, padx=5)
        self.download_button = ctk.CTkButton(self.file_frame, text="Download File", command=self.download_file)
        self.download_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = ctk.CTkButton(self.file_frame, text="Delete File", command=self.delete_file, fg_color="red", hover_color="darkred")
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.list_button = ctk.CTkButton(self.file_frame, text="List Files", command=self.list_files)
        self.list_button.pack(side=tk.LEFT, padx=5)

        # Initialize socket
        self.client_socket = None
        self.client_name = None
        self.running = False
        self.receiving_file = False

    def log_message(self, message):
        self.root.after(0, lambda: self._log_message(message))

    def _log_message(self, message):
        self.message_log.configure(state='normal')
        self.message_log.insert(tk.END, message + '\n')
        self.message_log.configure(state='disabled')
        self.message_log.yview(tk.END)
        logger.info(message)

    def start_connect_thread(self):
        if self.running:
            self.log_message("Already connected")
            return
        self.connect_button.configure(state='disabled')
        threading.Thread(target=self.connect_to_server, daemon=True).start()

    def connect_to_server(self):
        self.client_name = self.name_entry.get().strip()
        host = self.ip_entry.get().strip()
        if not self.client_name or not host:
            self.log_message("Please enter a name and server IP")
            self.root.after(0, lambda: self.connect_button.configure(state='normal'))
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5.0)
            self.client_socket.connect((host, PORT))
            self.client_socket.send(self.client_name.encode('utf-8'))
            response = self.client_socket.recv(1024).decode('utf-8')
            response_data = json.loads(response)
            if response_data.get("status") == "error":
                self.log_message(f"Connection failed: {response_data.get('message')}")
                self.client_socket.close()
                self.client_socket = None
                self.root.after(0, lambda: self.connect_button.configure(state='normal'))
                return
            self.running = True
            self.root.after(0, lambda: self._update_gui_after_connect(host))
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            self.log_message(f"Connection error: {str(e)}")
            self.client_socket = None
            self.root.after(0, lambda: self.connect_button.configure(state='normal'))

    def _update_gui_after_connect(self, host):
        self.root.title(f"Client: {self.client_name}")
        self.log_message(f"Connected to server at {host}:{PORT} as {self.client_name}")
        self.name_entry.configure(state='disabled')
        self.ip_entry.configure(state='disabled')
        self.disconnect_button.configure(state='normal')

    def disconnect(self):
        if not self.running:
            self.log_message("Not connected")
            return
        self.running = False
        self.receiving_file = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        self.name_entry.configure(state='normal')
        self.ip_entry.configure(state='normal')
        self.connect_button.configure(state='normal')
        self.disconnect_button.configure(state='disabled')
        self.log_message("Disconnected from server")

    def receive_messages(self):
        while self.running:
            try:
                self.client_socket.settimeout(1.0)
                data = self.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                response = json.loads(data)
                command = response.get("command")
                if command == "MESSAGE":
                    self.log_message(f"{response.get('sender')}: {response.get('message')}")
                elif command == "LIST":
                    if response.get("status") == "success":
                        files = response.get("files", [])
                        self.log_message("Available files: " + ", ".join(files) if files else "No files available")
                    else:
                        self.log_message(f"List error: {response.get('message')}")
                elif command == "DOWNLOAD":
                    if response.get("status") == "success":
                        self.receiving_file = True
                        self.handle_download_response(response)
                        self.receiving_file = False
                    else:
                        self.log_message(f"Download error: {response.get('message')}")
                else:
                    self.log_message(f"Received: {response.get('message')}")
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                if self.receiving_file:
                    continue
                self.log_message("Error decoding server response")
            except Exception as e:
                self.log_message(f"Error receiving message: {str(e)}")
                break
        if self.running:
            self.disconnect()

    def send_message(self):
        if not self.client_socket or not self.running:
            self.log_message("Not connected to server")
            return
        message = self.message_entry.get().strip()
        if message:
            try:
                self.client_socket.send(json.dumps({"command": "MESSAGE", "message": message}).encode('utf-8'))
                self.log_message(f"Sent: {message}")
                self.message_entry.delete(0, tk.END)
            except Exception as e:
                self.log_message(f"Error sending message: {str(e)}")

    def upload_file(self):
        if not self.client_socket or not self.running:
            self.log_message("Not connected to server")
            return
        file_path = filedialog.askopenfilename()
        if file_path:
            filename = os.path.basename(file_path)
            try:
                file_size = os.path.getsize(file_path)
                self.client_socket.send(json.dumps({"command": "UPLOAD", "filename": filename, "file_size": file_size}).encode('utf-8'))
                with open(file_path, 'rb') as f:
                    while True:
                        data = f.read(1024)
                        if not data:
                            break
                        self.client_socket.send(data)
                self.log_message(f"Uploading {filename}...")
            except Exception as e:
                self.log_message(f"Error uploading {filename}: {str(e)}")

    def download_file(self):
        if not self.client_socket or not self.running:
            self.log_message("Not connected to server")
            return
        filename = self.message_entry.get().strip()
        if filename:
            try:
                self.client_socket.send(json.dumps({"command": "DOWNLOAD", "filename": filename}).encode('utf-8'))
                self.log_message(f"Requesting download of {filename}...")
            except Exception as e:
                self.log_message(f"Error requesting {filename}: {str(e)}")

    def handle_download_response(self, response):
        file_size = response.get("file_size")
        filename = response.get("filename")
        save_path = filedialog.asksaveasfilename(defaultextension=os.path.splitext(filename)[1], initialfile=filename)
        if save_path:
            try:
                received = 0
                self.client_socket.settimeout(5.0)
                with open(save_path, 'wb') as f:
                    while received < file_size:
                        data = self.client_socket.recv(1024)
                        if not data:
                            raise Exception("Connection closed during download")
                        f.write(data)
                        received += len(data)
                    if received != file_size:
                        raise Exception(f"Incomplete file received: {received}/{file_size} bytes")
                self.log_message(f"Downloaded {filename} to {save_path}")
            except Exception as e:
                self.log_message(f"Error downloading {filename}: {str(e)}")
            finally:
                self.client_socket.settimeout(1.0)

    def delete_file(self):
        if not self.client_socket or not self.running:
            self.log_message("Not connected to server")
            return
        filename = self.message_entry.get().strip()
        if filename:
            try:
                self.client_socket.send(json.dumps({"command": "DELETE", "filename": filename}).encode('utf-8'))
                self.log_message(f"Requesting deletion of {filename}...")
            except Exception as e:
                self.log_message(f"Error requesting deletion of {filename}: {str(e)}")

    def list_files(self):
        if not self.client_socket or not self.running:
            self.log_message("Not connected to server")
            return
        try:
            self.client_socket.send(json.dumps({"command": "LIST"}).encode('utf-8'))
            self.log_message("Requesting file list...")
        except Exception as e:
            self.log_message(f"Error requesting file list: {str(e)}")

    def on_closing(self):
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = ctk.CTk()
        app = ClientGUI(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)