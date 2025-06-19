import socket
import threading
import customtkinter as ctk
from tkinter import messagebox

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Socket Server (TCP & UDP)")
        self.root.geometry("700x500")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Get local IP address
        self.host = self.get_local_ip()

        # Main frame
        self.main_frame = ctk.CTkFrame(root, fg_color="transparent")
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Tabview for Communication and Logs
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(pady=10, padx=10, fill="both", expand=True)
        self.tabview.add("Communication")
        self.tabview.add("Logs")

        # Communication Tab
        comm_tab = self.tabview.tab("Communication")

        # Host and Port input frame
        self.input_frame = ctk.CTkFrame(comm_tab)
        self.input_frame.pack(pady=5, padx=5, fill="x")

        self.host_label = ctk.CTkLabel(self.input_frame, text="Host:", font=("Arial", 14))
        self.host_label.pack(side="left", padx=5)
        self.host_display = ctk.CTkLabel(self.input_frame, text=self.host, font=("Arial", 14), text_color="green")
        self.host_display.pack(side="left", padx=5)
        self.copy_ip_button = ctk.CTkButton(self.input_frame, text="Copy IP", command=self.copy_ip, font=("Arial", 12), width=80)
        self.copy_ip_button.pack(side="left", padx=5)

        self.port_label = ctk.CTkLabel(self.input_frame, text="Port:", font=("Arial", 14))
        self.port_label.pack(side="left", padx=5)
        self.port_entry = ctk.CTkEntry(self.input_frame, placeholder_text="12345", width=100, font=("Arial", 14))
        self.port_entry.pack(side="left", padx=5)
        self.port_entry.insert(0, "12345")

        self.start_button = ctk.CTkButton(self.input_frame, text="Start Server", command=self.start_server, font=("Arial", 14))
        self.start_button.pack(side="left", padx=10)
        self.stop_button = ctk.CTkButton(self.input_frame, text="Stop Server", command=self.stop_server, font=("Arial", 14), state="disabled", fg_color="red", hover_color="#CC0000", text_color="white")
        self.stop_button.pack(side="left", padx=10)

        # Client selection and response frame
        self.response_frame = ctk.CTkFrame(comm_tab)
        self.response_frame.pack(pady=5, padx=5, fill="x")

        self.client_label = ctk.CTkLabel(self.response_frame, text="Select Client:", font=("Arial", 14))
        self.client_label.pack(side="left", padx=5)
        self.client_dropdown = ctk.CTkOptionMenu(self.response_frame, values=["No clients"], width=200, font=("Arial", 14))
        self.client_dropdown.pack(side="left", padx=5)

        self.response_entry = ctk.CTkEntry(self.response_frame, placeholder_text="Enter response", width=200, font=("Arial", 14))
        self.response_entry.pack(side="left", padx=5)
        self.send_button = ctk.CTkButton(self.response_frame, text="Send Response", command=self.send_response, state="disabled", font=("Arial", 14))
        self.send_button.pack(side="left", padx=5)

        # Messages area
        self.messages_area = ctk.CTkTextbox(comm_tab, height=200, width=600, font=("Arial", 12))
        self.messages_area.pack(pady=10, padx=5, fill="both", expand=True)
        self.messages_area.insert("end", "Incoming Messages:\n")
        self.messages_area.configure(state="disabled")

        # Logs Tab
        logs_tab = self.tabview.tab("Logs")
        self.logs_area = ctk.CTkTextbox(logs_tab, height=300, width=600, font=("Arial", 12))
        self.logs_area.pack(pady=10, padx=5, fill="both", expand=True)
        self.logs_area.insert("end", "Server Logs:\n")
        self.logs_area.configure(state="disabled")

        # Client tracking
        self.clients = {}  # Format: {client_id: {"type": "TCP/UDP", "socket": socket_obj, "address": address, "active": bool}}
        self.client_id_counter = 0
        self.tcp_socket = None
        self.udp_socket = None
        self.running = False
        self.lock = threading.Lock()

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
        messagebox.showinfo("Success", "Server IP copied to clipboard!")

    def log(self, message, area="both"):
        if area in ["messages", "both"]:
            self.messages_area.configure(state="normal")
            self.messages_area.insert("end", message + "\n")
            self.messages_area.see("end")
            self.messages_area.configure(state="disabled")
        if area in ["logs", "both"]:
            self.logs_area.configure(state="normal")
            self.logs_area.insert("end", message + "\n")
            self.logs_area.see("end")
            self.logs_area.configure(state="disabled")

    def update_client_dropdown(self):
        with self.lock:
            client_ids = [f"{cid} ({info['type']} - {info['address']})" for cid, info in self.clients.items() if info["active"]]
            if not client_ids:
                client_ids = ["No clients"]
            self.client_dropdown.configure(values=client_ids)
            if client_ids != ["No clients"]:
                self.client_dropdown.set(client_ids[0])
            else:
                self.client_dropdown.set("No clients")

    def start_server(self):
        try:
            port = int(self.port_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
            return

        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.send_button.configure(state="normal")

        # Start TCP server
        threading.Thread(target=self.run_tcp_server, args=(self.host, port), daemon=True).start()
        # Start UDP server
        threading.Thread(target=self.run_udp_server, args=(self.host, port), daemon=True).start()
        self.log(f"Starting servers on {self.host}:{port}...")

    def run_tcp_server(self, host, port):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_socket.bind((host, port))
            self.tcp_socket.listen(5)
            self.log("TCP Server listening...")
            while self.running:
                try:
                    client_socket, client_address = self.tcp_socket.accept()
                    with self.lock:
                        client_id = f"Client-{self.client_id_counter}"
                        self.clients[client_id] = {
                            "type": "TCP",
                            "socket": client_socket,
                            "address": client_address,
                            "active": True
                        }
                        self.client_id_counter += 1
                    self.log(f"TCP: Connected to {client_address}", "both")
                    self.update_client_dropdown()
                    threading.Thread(target=self.handle_tcp_client, args=(client_id, client_socket, client_address), daemon=True).start()
                except Exception as e:
                    if self.running:
                        self.log(f"TCP Server error: {e}", "logs")
        except Exception as e:
            self.log(f"TCP Server error: {e}")
            self.running = False
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def handle_tcp_client(self, client_id, client_socket, client_address):
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8')
                self.log(f"TCP: Received from {client_address}: {message}", "both")
                # Send immediate acknowledgment
                response = "TCP: Message received by server!"
                client_socket.send(response.encode('utf-8'))
                self.log(f"TCP: Sent to {client_address}: {response}", "logs")
        except Exception as e:
            self.log(f"TCP Client {client_address} error: {e}", "logs")
        finally:
            with self.lock:
                if client_id in self.clients:
                    self.clients[client_id]["active"] = False
            client_socket.close()
            self.log(f"TCP: Disconnected from {client_address}", "both")
            self.update_client_dropdown()

    def run_udp_server(self, host, port):
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind((host, port))
            self.log("UDP Server listening...")
            while self.running:
                data, client_address = self.udp_socket.recvfrom(1024)
                message = data.decode('utf-8')
                with self.lock:
                    client_id = f"Client-{self.client_id_counter}"
                    self.clients[client_id] = {
                        "type": "UDP",
                        "socket": self.udp_socket,
                        "address": client_address,
                        "active": True
                    }
                    self.client_id_counter += 1
                self.log(f"UDP: Received from {client_address}: {message}", "both")
                self.update_client_dropdown()
                # Send immediate acknowledgment
                response = "UDP: Message received by server!"
                self.udp_socket.sendto(response.encode('utf-8'), client_address)
                self.log(f"UDP: Sent to {client_address}: {response}", "logs")
        except Exception as e:
            self.log(f"UDP Server error: {e}")
            self.running = False
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def send_response(self):
        selected_client = self.client_dropdown.get()
        if selected_client == "No clients":
            messagebox.showwarning("Warning", "No client selected")
            return
        response = self.response_entry.get()
        if not response:
            messagebox.showwarning("Warning", "Response cannot be empty")
            return

        client_id = selected_client.split(" ")[0]
        with self.lock:
            if client_id not in self.clients or not self.clients[client_id]["active"]:
                messagebox.showwarning("Warning", "Client no longer connected")
                self.update_client_dropdown()
                return
            client_info = self.clients[client_id]
            protocol = client_info["type"]
            address = client_info["address"]

        try:
            if protocol == "TCP":
                client_socket = client_info["socket"]
                client_socket.send(response.encode('utf-8'))
                self.log(f"TCP: Sent to {address}: {response}", "both")
            else:  # UDP
                self.udp_socket.sendto(response.encode('utf-8'), address)
                self.log(f"UDP: Sent to {address}: {response}", "both")
        except Exception as e:
            self.log(f"Error sending response to {address}: {e}", "logs")

    def stop_server(self):
        self.running = False
        with self.lock:
            for client_id, info in list(self.clients.items()):
                if info["type"] == "TCP" and info["active"]:
                    info["socket"].close()
                self.clients[client_id]["active"] = False
            self.clients.clear()
        if self.tcp_socket:
            self.tcp_socket.close()
        if self.udp_socket:
            self.udp_socket.close()
        self.log("Server stopped.", "both")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.update_client_dropdown()

    def stop(self):
        self.stop_server()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = ServerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.stop)
    root.mainloop()