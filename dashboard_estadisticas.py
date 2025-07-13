import customtkinter as ctk
import socket
import threading
import json
import pygame

class Dashboard(ctk.CTk):
    def __init__(self):
        super().__init__()

             # --- Reproducir música al iniciar ---
        pygame.mixer.init()
        try:
            pygame.mixer.music.load("assets/Dummy! - Toby Fox.mp3")
            pygame.mixer.music.play(-1)  # Repetir indefinidamente
        except Exception as e:
            print(f"Error al reproducir música: {e}")

        # --- Configuración de la Ventana ---
        self.title("Dashboard de Estadísticas del Puente")
        self.geometry("400x300")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- Widgets de la GUI ---
        self.title_label = ctk.CTkLabel(self, text="Estado del Sistema", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=20)

        self.frame = ctk.CTkFrame(self)
        self.frame.pack(pady=10, padx=20, fill="x")

        self.bridge_status_label = ctk.CTkLabel(self.frame, text="Estado del Puente: --", font=ctk.CTkFont(size=14))
        self.bridge_status_label.pack(pady=5, padx=10, anchor="w")
        
        self.direction_label = ctk.CTkLabel(self.frame, text="Dirección Actual: --", font=ctk.CTkFont(size=14))
        self.direction_label.pack(pady=5, padx=10, anchor="w")

        self.waiting_north_label = ctk.CTkLabel(self.frame, text="Carros esperando (Norte): --", font=ctk.CTkFont(size=14))
        self.waiting_north_label.pack(pady=5, padx=10, anchor="w")

        self.waiting_south_label = ctk.CTkLabel(self.frame, text="Carros esperando (Sur): --", font=ctk.CTkFont(size=14))
        self.waiting_south_label.pack(pady=5, padx=10, anchor="w")

        # --- NUEVO: Label para carros cruzando ---
        self.crossing_label = ctk.CTkLabel(self.frame, text="Carros cruzando: --", font=ctk.CTkFont(size=14))
        self.crossing_label.pack(pady=5, padx=10, anchor="w")

        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.error_label.pack(pady=10)

        # --- Iniciar el hilo de red ---
        self.network_thread = threading.Thread(target=self.listen_for_updates, daemon=True)
        self.network_thread.start()

    def listen_for_updates(self):
        HOST = '127.0.0.1'
        PORT = 65432
        
        while True: # Bucle para intentar reconectar si falla
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((HOST, PORT))
                self.error_label.configure(text="") # Limpiar error al conectar
                buffer = ""
                while True:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self.process_message(line)
            except Exception as e:
                self.error_label.configure(text=f"Error de conexión: {e}. Reintentando...")
                self.update_labels_with_error()
            finally:
                client_socket.close()
            # Esperar antes de reintentar la conexión
            import time
            time.sleep(5)
            
    def process_message(self, message):
        parts = message.strip().split(' ', 1)
        command = parts[0]
        if command == "STATUS_UPDATE" and len(parts) > 1:
            try:
                status_data = json.loads(parts[1])
                self.update_gui_labels(status_data)
            except json.JSONDecodeError:
                pass

    def update_gui_labels(self, data):
        status = data.get("bridge_status", "DESCONOCIDO")
        direction = data.get("current_direction") or "N/A"
        waiting_north = data.get("waiting_north", "?")
        waiting_south = data.get("waiting_south", "?")
        # --- NUEVO: obtener carros cruzando ---
        crossing_cars = data.get("crossing_cars", [])
        if isinstance(crossing_cars, list):
            crossing_str = ", ".join(str(cid) for cid in crossing_cars) if crossing_cars else "Ninguno"
        else:
            crossing_str = str(crossing_cars)

        if status == "FREE":
            self.bridge_status_label.configure(text="Estado del Puente: LIBRE", text_color="lightgreen")
        else:
            self.bridge_status_label.configure(text=f"Estado del Puente: OCUPADO", text_color="orange")

        self.direction_label.configure(text=f"Dirección Actual: {direction}")
        self.waiting_north_label.configure(text=f"Carros esperando (Norte): {waiting_north}")
        self.waiting_south_label.configure(text=f"Carros esperando (Sur): {waiting_south}")
        # --- NUEVO: actualizar label de carros cruzando ---
        self.crossing_label.configure(text=f"Carros cruzando: {crossing_str}")

    def update_labels_with_error(self):
        self.bridge_status_label.configure(text="Estado del Puente: DESCONOCIDO", text_color="red")
        self.direction_label.configure(text="Dirección Actual: N/A")
        self.waiting_north_label.configure(text="Carros esperando (Norte): ?")
        self.waiting_south_label.configure(text="Carros esperando (Sur): ?")
        self.crossing_label.configure(text="Carros cruzando: ?")

if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()