import customtkinter as ctk
import sys
import os
from PIL import Image
import main
import threading

class MenuApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURACIÓN DE LA VENTANA PRINCIPAL ---
        self.title("Menú Principal")
        self.geometry("550x450")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")

        self.simulacion_proc = None

        # --- CARGAR RECURSOS (IMÁGENES/ICONOS) ---
        # Asegúrate de tener una carpeta 'assets' con estas imágenes.
        try:
            self.bg_image = ctk.CTkImage(Image.open("assets/bridge_banner.png"), size=(550, 200))
            self.start_icon = ctk.CTkImage(Image.open("assets/start_icon.png"), size=(20, 20))
            self.stop_icon = ctk.CTkImage(Image.open("assets/stop_icon.png"), size=(20, 20))
        except FileNotFoundError:
            print("Advertencia: No se encontraron los archivos de imagen en la carpeta 'assets'.")
            self.bg_image = None
            self.start_icon = None
            self.stop_icon = None

        # --- INICIALIZAR LA INTERFAZ DE USUARIO ---
        self._crear_widgets()
        self.protocol("WM_DELETE_WINDOW", self.cerrar_todo) # Asegura que todo se cierre al presionar la 'X'

    def _crear_widgets(self):
        """Crea y posiciona todos los widgets en la ventana."""
        
        # --- IMAGEN DE CABECERA ---
        if self.bg_image:
            header_label = ctk.CTkLabel(self, text="", image=self.bg_image)
            header_label.pack()
        
        # --- MARCO PARA LOS CONTROLES ---
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(pady=20, padx=40, fill="both", expand=True)

        # --- TÍTULO Y DESCRIPCIÓN ---
        title = ctk.CTkLabel(frame, text="Simulador de Puente de Una Vía", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=(0, 10))

        description = ctk.CTkLabel(frame, 
                                   text="Gestión de tráfico con un servidor central y múltiples clientes (vehículos).",
                                   font=ctk.CTkFont(size=13),
                                   text_color="gray60",
                                   wraplength=450)
        description.pack(pady=(0, 25))

        # --- BOTONES DE ACCIÓN ---
        self.start_btn = ctk.CTkButton(frame, text="Iniciar Simulación", 
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       image=self.start_icon,
                                       fg_color="#28a745", hover_color="#218838",
                                       command=self.iniciar_simulacion)
        self.start_btn.pack(fill="x", pady=5, ipady=8)

        self.close_btn = ctk.CTkButton(frame, text="Cerrar Simulación", 
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       image=self.stop_icon,
                                       fg_color="#dc3545", hover_color="#c82333",
                                       command=self.cerrar_todo)
        self.close_btn.pack(fill="x", pady=5, ipady=8)
        self.close_btn.configure(state="disabled") # Deshabilitado al inicio

        # --- ETIQUETA DE ESTADO ---
        self.status_label = ctk.CTkLabel(frame, text="Simulación no iniciada.", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(15, 0))

    def iniciar_simulacion(self):
        """Inicia el proceso de simulación si no está activo usando SimulacionManager."""
        if self.simulacion_proc is None or (hasattr(self.simulacion_proc, "is_alive") and not self.simulacion_proc.is_alive()):
            try:
                self.simulacion_manager = main.SimulacionManager()
                self.simulacion_proc = threading.Thread(target=self.simulacion_manager.run, daemon=True)
                self.simulacion_proc.start()
                self.status_label.configure(text="Simulación iniciada con éxito.", text_color="#28a745")
                self.start_btn.configure(state="disabled")
                self.close_btn.configure(state="normal")
            except Exception as e:
                self.status_label.configure(text=f"Error al iniciar la simulación: {e}", text_color="#dc3545")
        else:
            self.status_label.configure(text="La simulación ya está en marcha.", text_color="orange")

    def cerrar_todo(self):
        """Termina el proceso de simulación y cierra la ventana del menú."""
        if hasattr(self, "simulacion_manager"):
            try:
                self.simulacion_manager.close_window()
                self.status_label.configure(text="Simulación cerrada.", text_color="gray60")
            except Exception as e:
                self.status_label.configure(text=f"Error al cerrar la simulación: {e}", text_color="#dc3545")
        else:
            self.status_label.configure(text="No había una simulación activa para cerrar.", text_color="gray60")

        self.start_btn.configure(state="normal")
        self.close_btn.configure(state="disabled")
        self.after(500, self.destroy)


if __name__ == "__main__":
    # Comprobar si Pillow está instalado
    try:
        from PIL import Image
    except ImportError:
        print("Error: La biblioteca 'Pillow' es necesaria para mostrar los iconos.")
        print("Por favor, instálala usando: pip install Pillow")
        sys.exit(1)

    # Crear la carpeta 'assets' si no existe, como ayuda al usuario
    if not os.path.exists("assets"):
        os.makedirs("assets")
        print("Se ha creado la carpeta 'assets'. Por favor, coloca 'bridge_banner.png', 'start_icon.png' y 'stop_icon.png' dentro.")

    app = MenuApp()
    app.mainloop()