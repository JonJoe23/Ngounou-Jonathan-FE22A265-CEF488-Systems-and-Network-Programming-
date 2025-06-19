import socket
import threading
import customtkinter as ctk
from tkinter import messagebox

class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Socket Client (TCP & UDP)")
        self.root.geometry("600x450")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Main frame
        self.main_frame = ctk.CTkFrame(root, fg_color="transparent")
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Server connection frame
        self.conn_frame = ctk.CTkFrame(self.main_frame)
        self.conn_frame.pack(pady=5, padx=5, fill="x")

        self.host_label = ctk.CTkLabel(self.conn_frame, text="Server Host:", font=("Arial", 14))
        self.host_label.pack(side="left", padx=5)
        self.host_entry = ctk.CTkEntry(self.conn_frame, placeholder_text="127.0.0.1", width=150, font=("Arial", 14))
        self.host_entry.pack(side="left", padx=5)
        self.host_entry.insert(0, "127.0.0.1")

        self.port_label = ctk.CTkLabel(self.conn_frame, text="Port:", font=("Arial", 14))
        self.port_label.pack(side="left", padx=5)
        self.port_entry = ctk.CTkEntry(self.conn_frame, placeholder_text="12345", width=100, font=("Arial", 14))
        self.port_entry.pack(side="left", padx=5)
        self.port_entry.insert(0, "12345")

        self.connect_button = ctk.CTkButton(self.conn_frame, text="Connect", command=self.connect_to_server, font=("Arial", 14))
        self.connect_button.pack(side="left", padx=5)
        self.disconnect_button = ctk.CTkButton(self.conn_frame, text="Disconnect", command=self.disconnect_from_server, font=("Arial", 14), state="disabled", fg_color="red", hover_color="#CC0000", text_color="white")
        self.disconnect_button.pack(side="left", padx=5)

        # Protocol and message frame
        self.msg_frame = ctk.CTkFrame(self.main_frame)
        self.msg_frame.pack(pady=5, padx=5, fill="x")

        self.protocol_label = ctk.CTkLabel(self.msg_frame, text="Protocol:", font=("Arial", 14))
        self.protocol_label.pack(side="left", padx=5)
        self.protocol = ctk.CTkOptionMenu(self.msg_frame, values=["TCP", "UDP"], command=self.update_protocol, width=100, font=("Arial", 14))
        self.protocol.pack(side="left", padx=5)

        self.message_entry = ctk.CTkEntry(self.msg_frame, placeholder_text="Enter message", width=200, font=("Arial", 14))
        self.message_entry.pack(side="left", padx=5)

        self.send_button = ctk.CTkButton(self.msg_frame, text="Send Message", command=self.send_message, font=("Arial", 14), state="disabled")
        self.send_button.pack(side="left", padx=5)

        # Log area and buttons
        self.log_frame = ctk.CTkFrame(self.main_frame)
        self.log_frame.pack(pady=5, padx=5, fill="both", expand=True)

        self.log_area = ctk.CTkTextbox(self.log_frame, height=200, width=500, font=("Arial", 12))
        self.log_area.pack(pady=5, padx=5, fill="both", expand=True)
        self.log_area.insert("end", "Client Log:\n")
        self.log_area.configure(state="disabled")

        self.clear_button = ctk.CTkButton(self.log_frame, text="Clear Log", command=self.clear_log, font=("Arial", 14))
        self.clear_button.pack(pady=5)

        self.current_protocol = "TCP"
        self.running = False
        self.connected = False
        self.tcp_socket = None
        self.udp_socket = None
        self.receive_thread = None

    def update_protocol(self, choice):
        self.current_protocol = choice
        self.log(f"Protocol set to: {choice}")

    def log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def clear_log(self):
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.insert("end", "Client Log:\n")
        self.log_area.configure(state="disabled")

    def connect_to_server(self):
        if self.connected:
            messagebox.showwarning("Warning", "Already connected to server")
            return

        host = self.host_entry.get()
        try:
            port = int(self.port_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
            return

        self.running = True
        self.connected = True
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.send_button.configure(state="normal")

        if self.current_protocol == "TCP":
            try:
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tcp_socket.connect((host, port))
                self.log(f"TCP: Connected to {host}:{port}")
                # Start a persistent receive thread
                self.receive_thread = threading.Thread(target=self.receive_tcp_messages, daemon=True)
                self.receive_thread.start()
            except Exception as e:
                self.log(f"TCP Connection error: {e}")
                self.disconnect_from_server()
        else:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.log(f"UDP: Ready to send to {host}:{port}")
            # Start a persistent receive thread for UDP
            self.receive_thread = threading.Thread(target=self.receive_udp_messages, daemon=True)
            self.receive_thread.start()

    def disconnect_from_server(self):
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to server")
            return

        self.running = False
        self.connected = False
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.send_button.configure(state="disabled")

        if self.current_protocol == "TCP" and self.tcp_socket:
            self.tcp_socket.close()
            self.tcp_socket = None
            self.log("TCP: Disconnected from server")
        elif self.current_protocol == "UDP" and self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None
            self.log("UDP: Disconnected from server")

    def receive_tcp_messages(self):
        while self.running and self.tcp_socket:
            try:
                self.tcp_socket.settimeout(1.0)  # Check every second
                data = self.tcp_socket.recv(1024)
                if not data:
                    break
                response = data.decode('utf-8')
                self.log(f"TCP: Received: {response}")
            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"TCP Receive error: {e}")
                break
        if self.tcp_socket:
            self.disconnect_from_server()

    def receive_udp_messages(self):
        while self.running and self.udp_socket:
            try:
                self.udp_socket.settimeout(1.0)  # Check every second
                response, server_address = self.udp_socket.recvfrom(1024)
                self.log(f"UDP: Received from {server_address}: {response.decode('utf-8')}")
            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"UDP Receive error: {e}")
                break

    def send_message(self):
        if not self.connected:
            messagebox.showwarning("Warning", "Not connected to server")
            return

        message = self.message_entry.get()
        if not message:
            messagebox.showwarning("Warning", "Message cannot be empty")
            return

        if self.current_protocol == "TCP":
            self.send_tcp_message(message)
        else:
            self.send_udp_message(message)

    def send_tcp_message(self, message):
        try:
            self.tcp_socket.send(message.encode('utf-8'))
            self.log(f"TCP: Sent: {message}")
        except Exception as e:
            self.log(f"TCP Send error: {e}")
            self.disconnect_from_server()

    def send_udp_message(self, message):
        host = self.host_entry.get()
        port = int(self.port_entry.get())
        try:
            self.udp_socket.sendto(message.encode('utf-8'), (host, port))
            self.log(f"UDP: Sent to {host}:{port}: {message}")
        except Exception as e:
            self.log(f"UDP Send error: {e}")

    def stop(self):
        self.disconnect_from_server()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = ClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.stop)
    root.mainloop()