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

        # --- BOTÓN ABOUT ---
        self.about_btn = ctk.CTkButton(frame, text="Acerca de", 
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color="#6c757d", hover_color="#5a6268",
                                       command=self.mostrar_about)
        self.about_btn.pack(fill="x", pady=5, ipady=8)

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

    def mostrar_about(self):
        """Muestra la ventana About con información del proyecto."""
        about_window = ctk.CTkToplevel(self)
        about_window.title("Acerca de - Simulador de Puente")
        about_window.geometry("500x600")
        about_window.resizable(False, False)
        about_window.transient(self)  # Mantiene la ventana siempre encima del menú principal
        about_window.grab_set()  # Hace la ventana modal
        
        # Centrar la ventana
        about_window.after(100, lambda: about_window.lift())
        
        # Marco principal con scroll
        main_frame = ctk.CTkScrollableFrame(about_window, corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Título principal
        title_label = ctk.CTkLabel(main_frame, 
                                   text="Simulador de Puente de Una Vía",
                                   font=ctk.CTkFont(size=28, weight="bold"))
        title_label.pack(pady=(0, 20))
        
        # Descripción del proyecto
        desc_label = ctk.CTkLabel(main_frame,
                                  text="Este proyecto simula la gestión de tráfico en un puente de una sola vía, utilizando una arquitectura distribuida con un servidor central y múltiples clientes (vehículos). Incluye una interfaz gráfica para visualizar el estado del puente, los vehículos y las operaciones de control.",
                                  font=ctk.CTkFont(size=14),
                                  wraplength=450,
                                  justify="left")
        desc_label.pack(pady=(0, 20), anchor="w")
        
        # Características principales
        features_title = ctk.CTkLabel(main_frame,
                                      text="Características principales:",
                                      font=ctk.CTkFont(size=18, weight="bold"))
        features_title.pack(pady=(10, 10), anchor="w")
        
        features_text = """• Simulación en tiempo real de tráfico en puente
• Arquitectura distribuida cliente-servidor
• Interfaz gráfica interactiva con pygame
• Control de semáforos y colas de espera
• Gestión justa del acceso al puente
• Panel de control con estadísticas en vivo
• Agregar y modificar vehículos dinámicamente
• Sistema de logs y eventos"""
        
        features_label = ctk.CTkLabel(main_frame,
                                      text=features_text,
                                      font=ctk.CTkFont(size=13),
                                      justify="left")
        features_label.pack(pady=(0, 20), anchor="w")
        
        # Tecnologías utilizadas
        tech_title = ctk.CTkLabel(main_frame,
                                  text="Tecnologías utilizadas:",
                                  font=ctk.CTkFont(size=18, weight="bold"))
        tech_title.pack(pady=(10, 10), anchor="w")
        
        tech_text = """• Python 3.8+
• pygame - Para la interfaz gráfica y simulación
• customtkinter - Para el menú y controles modernos
• Pillow - Para manejo de imágenes
• threading - Para programación concurrente
• socket - Para comunicación cliente-servidor"""
        
        tech_label = ctk.CTkLabel(main_frame,
                                  text=tech_text,
                                  font=ctk.CTkFont(size=13),
                                  justify="left")
        tech_label.pack(pady=(0, 20), anchor="w")
        
        # Componentes del sistema
        components_title = ctk.CTkLabel(main_frame,
                                        text="Componentes del sistema:",
                                        font=ctk.CTkFont(size=18, weight="bold"))
        components_title.pack(pady=(10, 10), anchor="w")
        
        components_text = """• servidor.py - Gestiona el acceso al puente y controla las colas
• interfaz.py - Visualización en tiempo real y control de vehículos  
• main.py - Administra el ciclo de vida de los procesos
• menu.py - Menú principal para iniciar la simulación"""
        
        components_label = ctk.CTkLabel(main_frame,
                                        text=components_text,
                                        font=ctk.CTkFont(size=13),
                                        justify="left")
        components_label.pack(pady=(0, 20), anchor="w")
        
        # Autores
        authors_title = ctk.CTkLabel(main_frame,
                                     text="Desarrolladores:",
                                     font=ctk.CTkFont(size=18, weight="bold"))
        authors_title.pack(pady=(10, 10), anchor="w")
        
        authors_text = """• Franmari Garcia
• Magleo Medina"""
        
        authors_label = ctk.CTkLabel(main_frame,
                                     text=authors_text,
                                     font=ctk.CTkFont(size=14),
                                     justify="left")
        authors_label.pack(pady=(0, 20), anchor="w")
        
        # Botón cerrar
        close_button = ctk.CTkButton(main_frame, 
                                     text="Cerrar",
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     command=about_window.destroy)
        close_button.pack(pady=20)


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