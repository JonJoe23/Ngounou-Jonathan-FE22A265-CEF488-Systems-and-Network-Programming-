import socket
import threading
import time
import json
import random
import customtkinter as ctk
from tkinter import ttk, scrolledtext
from typing import Dict, List, Tuple, Any

class DataCoordinator:
    def __init__(self, gui):
        self.host = self.get_local_ip()
        self.port = 9999
        self.socket = None
        self.gui = gui
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # Increase receive buffer
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # Increase send buffer
            self.socket.settimeout(5.0)
            self.socket.bind((self.host, self.port))
            self.gui.log_message(f"Coordinator started on {self.host}:{self.port}")
        except OSError as e:
            self.gui.log_message(f"Error: Port {self.port} already in use. Try another port.")
            return
        
        # Track workers and tasks
        self.workers: Dict[Tuple[str, int], dict] = {}
        self.pending_tasks: Dict[int, dict] = {}
        self.completed_tasks: Dict[int, Any] = {}
        self.task_counter = 0
        self.dataset_size = 100000
        self.lock = threading.Lock()
        self.max_chunk_size = 10000  # Limit per task to avoid UDP size limit
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"  # Fallback to localhost if unable to get IP
    
    def generate_sample_data(self, size):
        """Generate sample numerical data for processing"""
        return [random.randint(1, 1000) for _ in range(size)]
    
    def split_data(self, data: List[int], num_chunks: int) -> List[List[int]]:
        """Split data into smaller chunks to fit UDP limits"""
        chunk_size = min(self.max_chunk_size, len(data) // num_chunks)
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunks.append(data[i:i + chunk_size])
        return chunks
    
    def register_worker(self, worker_addr: Tuple[str, int]):
        """Register a new worker"""
        with self.lock:
            if worker_addr not in self.workers:
                self.workers[worker_addr] = {
                    'status': 'ready',
                    'last_seen': time.time(),
                    'tasks_completed': 0
                }
                self.gui.log_message(f"Worker registered: {worker_addr}")
                self.gui.update_workers(list(self.workers.keys()))
                return True
            return False
    
    def send_task(self, worker_addr: Tuple[str, int], chunk_id: int, data_chunk: List[int]):
        """Send a task to a worker with size check"""
        if not self.socket:
            self.gui.log_message("Error: Socket not initialized")
            return False
        task_data = {
            'type': 'TASK',
            'chunk_id': chunk_id,
            'data': data_chunk,
            'operation': 'sum_and_stats'
        }
        message = json.dumps(task_data).encode('utf-8')
        if len(message) > 64000:  # Approx. 64KB limit minus headers
            self.gui.log_message(f"Error: Task {chunk_id} too large ({len(message)} bytes). Splitting not implemented.")
            return False
        try:
            self.socket.sendto(message, worker_addr)
            with self.lock:
                self.pending_tasks[chunk_id] = {
                    'worker': worker_addr,
                    'data_size': len(data_chunk),
                    'sent_time': time.time()
                }
                self.workers[worker_addr]['status'] = 'busy'
            self.gui.log_message(f"Task {chunk_id} sent to {worker_addr} (data size: {len(data_chunk)})")
            self.gui.update_task_progress(len(self.pending_tasks), len(self.completed_tasks))
            return True
        except Exception as e:
            self.gui.log_message(f"Error sending task to {worker_addr}: {e}")
            return False
    
    def handle_result(self, chunk_id: int, result: dict, worker_addr: Tuple[str, int]):
        """Handle completed task result"""
        with self.lock:
            if chunk_id in self.pending_tasks:
                self.completed_tasks[chunk_id] = result
                del self.pending_tasks[chunk_id]
                if worker_addr in self.workers:
                    self.workers[worker_addr]['status'] = 'ready'
                    self.workers[worker_addr]['tasks_completed'] += 1
                    self.workers[worker_addr]['last_seen'] = time.time()
                self.gui.log_message(f"Task {chunk_id} completed by {worker_addr}")
                self.gui.add_result(chunk_id, result)
                self.gui.update_task_progress(len(self.pending_tasks), len(self.completed_tasks))
                return True
        return False
    
    def listen_for_messages(self):
        """Listen for messages from workers"""
        if not self.socket:
            self.gui.log_message("Cannot listen: Socket not initialized")
            return
        while True:
            try:
                data, addr = self.socket.recvfrom(65536)  # Match buffer size
                message = json.loads(data.decode('utf-8'))
                msg_type = message.get('type')
                if msg_type == 'REGISTER':
                    if self.register_worker(addr):
                        ack = json.dumps({'type': 'ACK', 'message': 'registered'})
                        self.socket.sendto(ack.encode('utf-8'), addr)
                elif msg_type == 'RESULT':
                    chunk_id = message.get('chunk_id')
                    result = message.get('result')
                    self.handle_result(chunk_id, result, addr)
                elif msg_type == 'HEARTBEAT':
                    with self.lock:
                        if addr in self.workers:
                            self.workers[addr]['last_seen'] = time.time()
                            self.gui.log_message(f"Heartbeat from {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                self.gui.log_message(f"Error handling message: {e}")
    
    def distribute_work(self, data: List[int]):
        """Distribute work among available workers"""
        self.gui.log_message(f"Starting work distribution for {len(data)} elements...")
        attempts = 0
        max_attempts = 10
        while len(self.workers) < 2 and attempts < max_attempts:
            self.gui.log_message(f"Waiting for 2 workers... ({len(self.workers)} registered)")
            time.sleep(2)
            attempts += 1
        if len(self.workers) < 2:
            self.gui.log_message(f"Error: Only {len(self.workers)} workers registered. Need 2.")
            return
        self.gui.log_message(f"Found {len(self.workers)} workers")
        num_workers = len(self.workers)
        chunks = self.split_data(data, num_workers * (len(data) // self.max_chunk_size + 1))  # More chunks for smaller sizes
        worker_addrs = list(self.workers.keys())
        start_time = time.time()
        for i, chunk in enumerate(chunks):
            worker_addr = worker_addrs[i % len(worker_addrs)]
            chunk_id = self.task_counter
            self.task_counter += 1
            self.send_task(worker_addr, chunk_id, chunk)
        self.gui.log_message(f"Waiting for {len(chunks)} tasks to complete...")
        while len(self.completed_tasks) < len(chunks):
            time.sleep(0.5)
            current_time = time.time()
            with self.lock:
                for chunk_id, task_info in list(self.pending_tasks.items()):
                    if current_time - task_info['sent_time'] > 30:
                        self.gui.log_message(f"Task {chunk_id} timed out, reassigning...")
                        self.send_task(task_info['worker'], chunk_id, task_info['data'])
        end_time = time.time()
        processing_time = end_time - start_time
        self.aggregate_results(processing_time)
    
    def aggregate_results(self, processing_time: float):
        """Aggregate results from all workers"""
        total_sum = 0
        total_count = 0
        min_val = float('inf')
        max_val = float('-inf')
        for chunk_id in sorted(self.completed_tasks.keys()):
            result = self.completed_tasks[chunk_id]
            total_sum += result['sum']
            total_count += result['count']
            min_val = min(min_val, result['min'])
            max_val = max(max_val, result['max'])
        average = total_sum / total_count if total_count > 0 else 0
        self.gui.update_final_result({
            'total_sum': total_sum,
            'total_count': total_count,
            'average': average,
            'min_val': min_val,
            'max_val': max_val,
            'processing_time': processing_time,
            'throughput': total_count / processing_time if processing_time > 0 else 0
        })
        self.gui.log_message(f"Processing complete in {processing_time:.2f} seconds")
    
    def start_processing(self, dataset_size: int):
        """Start processing in a separate thread"""
        self.dataset_size = dataset_size
        self.completed_tasks.clear()
        self.pending_tasks.clear()
        self.task_counter = 0
        self.gui.clear_results()
        threading.Thread(target=self.distribute_work, args=(self.generate_sample_data(self.dataset_size),), daemon=True).start()

class CoordinatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Distributed Data Processing - Coordinator")
        self.root.geometry("900x700")
        # Create widgets before initializing coordinator
        self.create_widgets()
        # Initialize coordinator after GUI widgets are set up
        self.coordinator = DataCoordinator(self)
        threading.Thread(target=self.coordinator.listen_for_messages, daemon=True).start()
    
    def create_widgets(self):
        """Create GUI widgets"""
        # Main frame
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Server info frame
        self.server_frame = ctk.CTkFrame(self.main_frame)
        self.server_frame.pack(pady=5, padx=5, fill="x")
        self.server_label = ctk.CTkLabel(self.server_frame, text="Coordinator IP:")
        self.server_label.pack(side="left", padx=5)
        self.server_ip_label = ctk.CTkLabel(self.server_frame, text="Detecting...", text_color="green")
        self.server_ip_label.pack(side="left", padx=5)
        self.copy_ip_button = ctk.CTkButton(self.server_frame, text="Copy IP", command=self.copy_ip, width=80)
        self.copy_ip_button.pack(side="left", padx=5)
        
        # Control frame
        self.control_frame = ctk.CTkFrame(self.main_frame)
        self.control_frame.pack(pady=5, padx=5, fill="x")
        
        self.dataset_label = ctk.CTkLabel(self.control_frame, text="Dataset Size:")
        self.dataset_label.pack(side="left", padx=5)
        self.dataset_entry = ctk.CTkEntry(self.control_frame, width=150)
        self.dataset_entry.insert(0, "100000")
        self.dataset_entry.pack(side="left", padx=5)
        
        self.start_button = ctk.CTkButton(self.control_frame, text="Start Processing", command=self.start_processing)
        self.start_button.pack(side="left", padx=5)
        
        # Status log
        self.log_label = ctk.CTkLabel(self.main_frame, text="Status Log:")
        self.log_label.pack(pady=5)
        self.log_text = scrolledtext.ScrolledText(self.main_frame, height=6, wrap="word", state="disabled")
        self.log_text.pack(pady=5, padx=10, fill="x")
        
        # Workers
        self.workers_label = ctk.CTkLabel(self.main_frame, text="Workers: None")
        self.workers_label.pack(pady=5)
        
        # Progress
        self.progress_label = ctk.CTkLabel(self.main_frame, text="Tasks: 0 completed / 0 total")
        self.progress_label.pack(pady=5)
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5, padx=20, fill="x")
        
        # Results table
        self.results_frame = ctk.CTkFrame(self.main_frame)
        self.results_frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.results_tree = ttk.Treeview(self.results_frame, columns=("Chunk ID", "Sum", "Count", "Min", "Max"), show="headings")
        self.results_tree.heading("Chunk ID", text="Chunk ID")
        self.results_tree.heading("Sum", text="Sum")
        self.results_tree.heading("Count", text="Count")
        self.results_tree.heading("Min", text="Min")
        self.results_tree.heading("Max", text="Max")
        self.results_tree.pack(fill="both", expand=True)
        
        # Final results
        self.final_result_label = ctk.CTkLabel(self.main_frame, text="Final Results: None")
        self.final_result_label.pack(pady=5)
        
        # Update IP display after coordinator initialization
        self.root.after(100, self.update_ip_display)
    
    def update_ip_display(self):
        """Update the IP label with the coordinator's IP"""
        self.server_ip_label.configure(text=self.coordinator.host)
    
    def copy_ip(self):
        """Copy the coordinator's IP to the clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.coordinator.host)
        self.log_message("Coordinator IP copied to clipboard!")
    
    def log_message(self, message: str):
        """Add message to status log"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')}: {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def update_workers(self, workers: List[Tuple[str, int]]):
        """Update workers list"""
        self.workers_label.configure(text=f"Workers: {', '.join([f'{w[0]}:{w[1]}' for w in workers])}")
    
    def update_task_progress(self, pending: int, completed: int):
        """Update task progress"""
        total = pending + completed
        self.progress_label.configure(text=f"Tasks: {completed} completed / {total} total")
        self.progress_bar.set(completed / total if total > 0 else 0)
    
    def add_result(self, chunk_id: int, result: dict):
        """Add result to table"""
        self.results_tree.insert("", "end", values=(chunk_id, result['sum'], result['count'], result['min'], result['max']))
    
    def clear_results(self):
        """Clear results table"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.final_result_label.configure(text="Final Results: None")
    
    def update_final_result(self, result: dict):
        """Update final aggregated results"""
        text = (
            f"Final Results:\n"
            f"Total Elements: {result['total_count']:,}\n"
            f"Total Sum: {result['total_sum']:,}\n"
            f"Average: {result['average']:.2f}\n"
            f"Minimum: {result['min_val']}\n"
            f"Maximum: {result['max_val']}\n"
            f"Processing Time: {result['processing_time']:.2f} seconds\n"
            f"Throughput: {result['throughput']:.0f} elements/second"
        )
        self.final_result_label.configure(text=text)
    
    def start_processing(self):
        """Start processing with user-specified dataset size"""
        try:
            dataset_size = int(self.dataset_entry.get())
            if dataset_size <= 0:
                self.log_message("Error: Dataset size must be positive")
                return
            self.coordinator.start_processing(dataset_size)
            self.log_message("Processing started...")
        except ValueError:
            self.log_message("Error: Invalid dataset size")

if __name__ == "__main__":
    ctk.set_default_color_theme("dark-blue")
    app = ctk.CTk()
    gui = CoordinatorGUI(app)
    app.mainloop()