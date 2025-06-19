import socket
import json
import sys
import time
import threading
import customtkinter as ctk
from tkinter import ttk, scrolledtext
from tkinter import messagebox
from typing import Tuple

class Worker:
    def __init__(self, gui, port=10000):
        self.host = ''  # Bind to all interfaces
        self.port = port
        self.coordinator_addr = None  # Will be set via GUI
        self.gui = gui
        self.socket = None
        self.is_running = False
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # Increase receive buffer
            self.socket.settimeout(5.0)
            self.socket.bind((self.host, port))
            self.gui.log_message(f"Worker initialized on port {port}")
        except OSError as e:
            self.gui.log_message(f"Error: Port {port} already in use. Try another port.")
    
    def process_task(self, data: list) -> dict:
        """Process a data chunk and compute statistics"""
        if not data:
            return {'sum': 0, 'count': 0, 'min': 0, 'max': 0}
        total = sum(data)
        count = len(data)
        return {
            'sum': total,
            'count': count,
            'min': min(data),
            'max': max(data)
        }
    
    def send_heartbeat(self):
        """Send periodic heartbeat to coordinator"""
        while self.is_running and self.coordinator_addr:
            try:
                if self.socket:
                    message = json.dumps({'type': 'HEARTBEAT'}).encode('utf-8')
                    self.socket.sendto(message, self.coordinator_addr)
                    self.gui.log_message(f"Sent heartbeat to coordinator {self.coordinator_addr}")
                time.sleep(5)
            except Exception as e:
                self.gui.log_message(f"Error sending heartbeat: {e}")
    
    def run(self):
        """Main worker loop"""
        if not self.socket:
            self.gui.log_message("Cannot run worker: Socket not initialized")
            return
        if not self.coordinator_addr:
            self.gui.log_message("Error: Coordinator IP not set")
            messagebox.showerror("Error", "Please enter a valid Coordinator IP")
            return
        self.is_running = True
        
        # Register with coordinator
        attempts = 0
        max_attempts = 5
        while attempts < max_attempts and self.is_running:
            try:
                register_msg = json.dumps({'type': 'REGISTER'}).encode('utf-8')
                self.socket.sendto(register_msg, self.coordinator_addr)
                self.gui.log_message(f"Attempting to register with coordinator {self.coordinator_addr} (Attempt {attempts + 1}/{max_attempts})")
                data, addr = self.socket.recvfrom(65536)
                message = json.loads(data.decode('utf-8'))
                if message.get('type') == 'ACK':
                    self.gui.log_message("Registered with coordinator")
                    self.gui.update_status("Connected")
                    break
            except socket.timeout:
                attempts += 1
                self.gui.log_message(f"Registration attempt {attempts}/{max_attempts} failed. Retrying...")
                time.sleep(2)
            except Exception as e:
                self.gui.log_message(f"Error during registration: {e}")
                return
        if attempts >= max_attempts:
            self.gui.log_message("Error: Failed to register with coordinator")
            self.gui.update_status("Disconnected")
            self.is_running = False
            return
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        # Main loop for receiving tasks
        while self.is_running:
            try:
                data, addr = self.socket.recvfrom(65536)
                message = json.loads(data.decode('utf-8'))
                if message.get('type') == 'TASK':
                    chunk_id = message.get('chunk_id')
                    chunk_data = message.get('data')
                    self.gui.log_message(f"Received task {chunk_id} with {len(chunk_data)} elements")
                    self.gui.add_task(chunk_id, len(chunk_data))
                    result = self.process_task(chunk_data)
                    response = json.dumps({
                        'type': 'RESULT',
                        'chunk_id': chunk_id,
                        'result': result
                    }).encode('utf-8')
                    self.socket.sendto(response, self.coordinator_addr)
                    self.gui.log_message(f"Sent result for task {chunk_id}")
                    self.gui.add_result(chunk_id, result)
                elif message.get('type') == 'ACK':
                    self.gui.log_message("Received registration acknowledgment")
            except socket.timeout:
                continue
            except Exception as e:
                self.gui.log_message(f"Error processing message: {e}")
    
    def start_connect(self):
        """Start the worker loop in a thread"""
        if not self.is_running:
            threading.Thread(target=self.run, daemon=True).start()

class WorkerGUI:
    def __init__(self, root, port):
        self.root = root
        self.root.title(f"Distributed Data Processing - Worker {port}")
        self.root.geometry("700x500")
        # Create widgets first
        self.create_widgets()
        # Initialize worker after widgets are set up
        self.worker = Worker(self, port=port)
    
    def create_widgets(self):
        """Create GUI widgets"""
        # Main frame
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Coordinator IP frame
        self.coord_frame = ctk.CTkFrame(self.main_frame)
        self.coord_frame.pack(pady=5, padx=5, fill="x")
        self.coord_label = ctk.CTkLabel(self.coord_frame, text="Coordinator IP:")
        self.coord_label.pack(side="left", padx=5)
        self.coord_entry = ctk.CTkEntry(self.coord_frame, placeholder_text="Enter Coordinator IP", width=150)
        self.coord_entry.pack(side="left", padx=5)
        
        # Control frame
        self.control_frame = ctk.CTkFrame(self.main_frame)
        self.control_frame.pack(pady=5, padx=5, fill="x")
        
        self.status_label = ctk.CTkLabel(self.control_frame, text="Status: Disconnected")
        self.status_label.pack(side="left", padx=5)
        
        self.connect_button = ctk.CTkButton(self.control_frame, text="Connect", command=self.start_connect)
        self.connect_button.pack(side="left", padx=5)
        
        # Status log
        self.log_label = ctk.CTkLabel(self.main_frame, text="Status Log:")
        self.log_label.pack(pady=5)
        self.log_text = scrolledtext.ScrolledText(self.main_frame, height=6, wrap="word", state="disabled")
        self.log_text.pack(pady=5, padx=10, fill="x")
        
        # Progress
        self.progress_label = ctk.CTkLabel(self.main_frame, text="Task Progress: 0%")
        self.progress_label.pack(pady=5)
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5, padx=20, fill="x")
        
        # Tasks table
        self.tasks_frame = ctk.CTkFrame(self.main_frame)
        self.tasks_frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.tasks_tree = ttk.Treeview(self.tasks_frame, columns=("Task ID", "Data Size", "Sum", "Count", "Min", "Max"), show="headings")
        self.tasks_tree.heading("Task ID", text="Task ID")
        self.tasks_tree.heading("Data Size", text="Data Size")
        self.tasks_tree.heading("Sum", text="Sum")
        self.tasks_tree.heading("Count", text="Count")
        self.tasks_tree.heading("Min", text="Min")
        self.tasks_tree.heading("Max", text="Max")
        self.tasks_tree.pack(fill="both", expand=True)
        
        self.task_count = 0
        self.completed_tasks = 0
    
    def log_message(self, message: str):
        """Add message to status log"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')}: {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def update_status(self, status: str):
        """Update status label"""
        self.status_label.configure(text=f"Status: {status}")
    
    def add_task(self, task_id: int, data_size: int):
        """Add task to table"""
        self.task_count += 1
        self.tasks_tree.insert("", "end", values=(task_id, data_size, "-", "-", "-", "-"))
        self.update_task_progress()
    
    def add_result(self, task_id: int, result: dict):
        """Update task with result in table"""
        self.completed_tasks += 1
        for item in self.tasks_tree.get_children():
            if self.tasks_tree.item(item, "values")[0] == str(task_id):
                self.tasks_tree.item(item, values=(task_id, self.tasks_tree.item(item, "values")[1], result['sum'], result['count'], result['min'], result['max']))
                break
        self.update_task_progress()
    
    def update_task_progress(self):
        """Update task progress"""
        progress = self.completed_tasks / self.task_count if self.task_count > 0 else 0
        self.progress_label.configure(text=f"Task Progress: {progress * 100:.0f}%")
        self.progress_bar.set(progress)
    
    def start_connect(self):
        """Start the worker loop with coordinator IP from entry"""
        try:
            coord_ip = self.coord_entry.get().strip()
            if not coord_ip:
                self.log_message("Error: Coordinator IP cannot be empty")
                messagebox.showerror("Error", "Please enter a valid Coordinator IP")
                return
            self.worker.coordinator_addr = (coord_ip, 9999)  # Coordinator port is fixed at 9999
            self.worker.start_connect()
        except Exception as e:
            self.log_message(f"Error setting coordinator IP: {e}")
            messagebox.showerror("Error", f"Invalid Coordinator IP: {e}")

if __name__ == "__main__":
    ctk.set_default_color_theme("dark-blue")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    app = ctk.CTk()
    gui = WorkerGUI(app, port)
    app.mainloop()