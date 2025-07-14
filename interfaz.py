import pygame
import socket
import threading
import random
import sys
import time
import customtkinter as ctk
import json
from collections import deque
import textwrap

# --- Constantes de Configuración de Pygame ---
SIM_WIDTH, PANEL_WIDTH = 900, 350
SCREEN_WIDTH, SCREEN_HEIGHT = SIM_WIDTH + PANEL_WIDTH, 600
BRIDGE_Y_CENTER = SCREEN_HEIGHT / 2
BRIDGE_HEIGHT = 80
BRIDGE_START_X, BRIDGE_END_X = 200, 700
CAR_WIDTH, CAR_HEIGHT = 30, 20
FPS = 60

# --- Constantes de Colisión y Diseño ---
SAFE_DISTANCE_ON_BRIDGE = 25
QUEUE_GAP = 10
LANE_LINE_WIDTH, LANE_LINE_HEIGHT = 20, 5
LANE_LINE_GAP = 20

# --- Colores ---
WHITE, BLACK, GRAY = (255, 255, 255), (0, 0, 0), (150, 150, 150)
ROAD_COLOR, GRASS_COLOR, RIVER_COLOR = (50, 50, 50), (34, 139, 34), (70, 130, 180)
BUTTON_COLOR, BUTTON_TEXT_COLOR = (100, 100, 200), WHITE
PANEL_BG_COLOR = (20, 20, 40)
GREEN_LIGHT, RED_LIGHT, OFF_LIGHT = (0, 255, 0), (255, 0, 0), (80, 80, 80)
PROGRESS_BAR_BG = (60, 60, 80)
PROGRESS_BAR_FG = (100, 100, 220)

# --- Estado compartido y Thread-safety ---
carros_lock = threading.Lock()
status_lock = threading.Lock()
current_server_status = {}
event_log = deque(maxlen=13)

class Carro:
    def __init__(self, car_id, direction, speed, delay_time):
        self.id = car_id
        self.direction = direction
        self.color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
        self.original_speed = speed
        self.delay_time = delay_time
        self.speed = self.original_speed
        y_pos = (BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 4 - CAR_HEIGHT) if direction == 'NORTH' else (BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 4)
        self.original_y = y_pos
        
        # --- LÍNEA A CORREGIR ---
        # La posición inicial de los carros del SUR debe ajustarse por su propio ancho.
        self.start_pos_x = -CAR_WIDTH if direction == 'NORTH' else (SIM_WIDTH - CAR_WIDTH)
        
        self.rect = pygame.Rect(self.start_pos_x, self.original_y, CAR_WIDTH, CAR_HEIGHT)
        self.state = 'IDLE'

    def reset_position_and_direction(self):
        self.direction = 'SOUTH' if self.direction == 'NORTH' else 'NORTH'
        self.original_y = (BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 4 - CAR_HEIGHT) if self.direction == 'NORTH' else (BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 4)
        self.start_pos_x = -CAR_WIDTH if self.direction == 'NORTH' else SIM_WIDTH
        self.rect.x, self.rect.y = self.start_pos_x, self.original_y

    def update(self, all_cars):
        self.speed = self.original_speed
        # --- Lógica de la cola de espera ---
        if self.state in ['DRIVING_TO_BRIDGE', 'WAITING']:
            front_car = None
            min_dist = float('inf')
            for other in all_cars:
                if other.id != self.id and other.direction == self.direction and other.state in ['WAITING', 'DRIVING_TO_BRIDGE']:
                    if self.direction == 'NORTH' and self.rect.x < other.rect.x:
                        dist = other.rect.x - self.rect.x
                        if dist < min_dist: min_dist, front_car = dist, other
                    elif self.direction == 'SOUTH' and self.rect.x > other.rect.x:
                        dist = self.rect.x - other.rect.x
                        if dist < min_dist: min_dist, front_car = dist, other
            
            if self.direction == 'NORTH':
                target_x = (front_car.rect.left - QUEUE_GAP - CAR_WIDTH) if front_car else (BRIDGE_START_X - 20 - CAR_WIDTH)
                if self.rect.x < target_x:
                    self.rect.x += self.speed
                    # Limitar para no pasar el borde de simulación
                    if self.rect.right > SIM_WIDTH:
                        self.rect.x = SIM_WIDTH - CAR_WIDTH
                else:
                    self.rect.x, self.state = target_x, 'WAITING'
            else: # SOUTH
                target_x = (front_car.rect.right + QUEUE_GAP) if front_car else (BRIDGE_END_X + 20)
                if self.rect.x > target_x:
                    self.rect.x -= self.speed
                    if self.rect.x < 0:
                        self.rect.x = 0
                else:
                    self.rect.x, self.state = target_x, 'WAITING'
        
        # --- Lógica de cruce en el puente ---
        elif self.state == 'CROSSING':
            self.rect.y = BRIDGE_Y_CENTER - CAR_HEIGHT / 2
            for other in all_cars:
                if other.id != self.id and other.direction == self.direction and other.state == 'CROSSING':
                    if self.direction == 'NORTH' and other.rect.x > self.rect.x and other.rect.x - self.rect.right < SAFE_DISTANCE_ON_BRIDGE:
                        self.speed = 0; break
                    elif self.direction == 'SOUTH' and other.rect.x < self.rect.x and self.rect.left - other.rect.right < SAFE_DISTANCE_ON_BRIDGE:
                        self.speed = 0; break
            
            if self.direction == 'NORTH':
                if self.rect.x < BRIDGE_END_X: self.rect.x += self.speed
                else: self.state = 'RETURNING'
            else:
                if self.rect.right > BRIDGE_START_X: self.rect.x -= self.speed
                else: self.state = 'RETURNING'
        
        # --- Lógica de salida de la simulación ---
        elif self.state == 'RETURNING':
            self.rect.y = self.original_y
            if self.direction == 'NORTH':
                # --- LÍNEA CORREGIDA ---
                # Se elimina "+ CAR_WIDTH" para que el carro desaparezca justo en el borde.
                if self.rect.x < SIM_WIDTH: 
                    self.rect.x += self.speed
                else: 
                    self.state = 'IDLE'
            else: # SOUTH
                # Esta parte ya era correcta
                if self.rect.right > -CAR_WIDTH: 
                    self.rect.x -= self.speed
                else: 
                    self.state = 'IDLE'

    def draw(self, screen, font):
        pygame.draw.rect(screen, self.color, self.rect)
        id_render = font.render(str(self.id), True, BLACK)
        screen.blit(id_render, (self.rect.centerx - id_render.get_width() / 2, self.rect.centery - id_render.get_height() / 2))
        
        # Dibujar luces de freno
        if self.speed == 0 and self.state in ['WAITING', 'CROSSING']:
            if self.direction == 'NORTH': # Yendo a la derecha
                brake_rect = pygame.Rect(self.rect.left - 3, self.rect.centery - 2, 3, 4)
            else: # Yendo a la izquierda
                brake_rect = pygame.Rect(self.rect.right, self.rect.centery - 2, 3, 4)
            pygame.draw.rect(screen, RED_LIGHT, brake_rect)


def carro_lifecycle(carro: Carro):
    """Ciclo de vida y lógica de red para un carro."""
    HOST, PORT = '127.0.0.1', 65432
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
        except ConnectionRefusedError:
            carro.state = 'ERROR'; return
        while True:
            carro.state = 'IDLE'
            carro.rect.x, carro.rect.y = carro.start_pos_x, carro.original_y
            carro.speed = carro.original_speed
            time.sleep(carro.delay_time)

            carro.state = 'DRIVING_TO_BRIDGE'
            while carro.state == 'DRIVING_TO_BRIDGE': time.sleep(0.1)

            carro.state = 'WAITING'
            s.sendall(f"REQUEST_CROSS {carro.direction} {carro.id}\n".encode('utf-8'))
            while True:
                try:
                    data = s.recv(1024).decode('utf-8')
                    if not data: carro.state = 'ERROR'; return
                    if 'GRANT_CROSS' in data: break
                except (ConnectionAbortedError, ConnectionResetError):
                    carro.state = 'ERROR'; return

            carro.state = 'CROSSING'
            while carro.state == 'CROSSING': time.sleep(0.1)

            s.sendall("RELEASE_BRIDGE\n".encode('utf-8'))
            while carro.state == 'RETURNING': time.sleep(0.1)
            carro.reset_position_and_direction()

def listen_for_server_updates():
    """Hilo dedicado a escuchar al servidor y actualizar el estado global."""
    global current_server_status, event_log
    HOST, PORT = '127.0.0.1', 65432
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((HOST, PORT))
            buffer = ""
            while True:
                data = client_socket.recv(4096).decode('utf-8')
                if not data: break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    parts = line.strip().split(' ', 1)
                    if parts[0] == "STATUS_UPDATE" and len(parts) > 1:
                        try:
                            status_data = json.loads(parts[1])
                            with status_lock:
                                current_server_status = status_data
                                if 'log' in status_data:
                                    event_log.clear()
                                    event_log.extend(status_data['log'])
                        except json.JSONDecodeError:
                            print("Error decodificando JSON del servidor")
        except Exception as e:
            print(f"Error de conexión con el servidor: {e}. Reintentando en 5s...")
            with status_lock:
                current_server_status = {"error": "Servidor no conectado"}
        finally:
            client_socket.close()
            time.sleep(5)

def abrir_formulario_agregar_carro(lista_carros, lock):
    """Formulario de customtkinter para agregar un carro con ID automático y sliders."""
    app = ctk.CTk()
    app.title("Agregar Nuevo Carro")
    app.geometry("350x450")
    
    with lock:
        max_id = max([c.id for c in lista_carros] or [0])
        next_id = max_id + 1

    frame = ctk.CTkFrame(app); frame.pack(pady=20, padx=20, fill="both", expand=True)

    ctk.CTkLabel(frame, text="ID del Carro (Automático):").pack(pady=5)
    id_entry = ctk.CTkEntry(frame, placeholder_text=str(next_id))
    id_entry.insert(0, str(next_id)); id_entry.configure(state="disabled"); id_entry.pack()
    
    # --- Slider para Velocidad ---
    ctk.CTkLabel(frame, text="Velocidad:").pack(pady=(10, 0))
    speed_value_label = ctk.CTkLabel(frame, text="3.0")
    speed_value_label.pack()
    speed_slider = ctk.CTkSlider(frame, from_=1, to=8, number_of_steps=14, command=lambda v: speed_value_label.configure(text=f"{v:.1f}"))
    speed_slider.set(3.0); speed_slider.pack()

    # --- Slider para Descanso ---
    ctk.CTkLabel(frame, text="Tiempo de Descanso (segundos):").pack(pady=(10, 0))
    delay_value_label = ctk.CTkLabel(frame, text="5.0")
    delay_value_label.pack()
    delay_slider = ctk.CTkSlider(frame, from_=2, to=15, number_of_steps=13, command=lambda v: delay_value_label.configure(text=f"{v:.1f}"))
    delay_slider.set(5.0); delay_slider.pack()

    ctk.CTkLabel(frame, text="Dirección Inicial:").pack(pady=(10, 0))
    direction_var = ctk.StringVar(value="NORTH")
    ctk.CTkOptionMenu(frame, values=["NORTH", "SOUTH"], variable=direction_var).pack()
    
    error_label = ctk.CTkLabel(frame, text="", text_color="red"); error_label.pack(pady=5)

    def procesar_nuevo_carro():
        try:
            nuevo_carro = Carro(
                car_id=next_id,
                direction=direction_var.get(),
                speed=float(speed_slider.get()),
                delay_time=float(delay_slider.get())
            )
            with lock:
                lista_carros.append(nuevo_carro)
            thread = threading.Thread(target=carro_lifecycle, args=(nuevo_carro,), daemon=True); thread.start()
            app.destroy()
        except Exception as e:
            error_label.configure(text=f"Error inesperado: {e}")

    ctk.CTkButton(app, text="Confirmar", command=procesar_nuevo_carro).pack(pady=20)
    app.mainloop()

def abrir_formulario_modificar_carro(lista_carros, lock):
    import tkinter.messagebox as tkmsg

    app = ctk.CTk()
    app.title("Modificar Vehículo")
    app.geometry("350x400")

    # --- Usar CTkScrollableFrame en vez de CTkFrame ---
    scroll_frame = ctk.CTkScrollableFrame(app)
    scroll_frame.pack(pady=20, padx=20, fill="both", expand=True)

    def mostrar_lista_ids():
        for widget in scroll_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(scroll_frame, text="Selecciona un ID de Carro:", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        with lock:
            carros_actuales = list(lista_carros)
        for carro in carros_actuales:
            btn = ctk.CTkButton(scroll_frame, text=f"ID: {carro.id}", font=ctk.CTkFont(size=14),
                                command=lambda c=carro: mostrar_estadisticas_carro(c))
            btn.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(scroll_frame, text="Cerrar", command=app.destroy).pack(pady=15)

    def mostrar_estadisticas_carro(carro):
        for widget in scroll_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(scroll_frame, text=f"Estadísticas del Carro ID: {carro.id}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkLabel(scroll_frame, text=f"Dirección: {carro.direction}", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=3)

        # Velocidad modificable (formateada a 2 decimales)
        ctk.CTkLabel(scroll_frame, text="Velocidad:", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=(10,0))
        velocidad_entry = ctk.CTkEntry(scroll_frame)
        velocidad_entry.insert(0, f"{round(carro.original_speed, 2)}")
        velocidad_entry.pack(anchor="w", padx=10, pady=2)

        # Descanso modificable (formateada a 2 decimales)
        ctk.CTkLabel(scroll_frame, text="Descanso (s):", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=(10,0))
        descanso_entry = ctk.CTkEntry(scroll_frame)
        descanso_entry.insert(0, f"{round(carro.delay_time, 2)}")
        descanso_entry.pack(anchor="w", padx=10, pady=2)

        ctk.CTkLabel(scroll_frame, text=f"Estado actual: {carro.state}", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=10)

        def guardar_config():
            try:
                speed_raw = velocidad_entry.get()
                delay_raw = descanso_entry.get()
                if speed_raw == "" or delay_raw == "":
                    tkmsg.showerror("Error", "Debes ingresar valores numéricos en ambos campos.")
                    return
                new_speed = round(float(speed_raw), 2)
                new_delay = round(float(delay_raw), 2)
                if new_speed == 0 or new_delay == 0:
                    tkmsg.showerror("Error", "La velocidad y el tiempo de descanso no pueden ser 0.")
                    return
                with lock:
                    carro.original_speed = new_speed
                    carro.delay_time = new_delay
                tkmsg.showinfo("Guardado", "Configuración guardada correctamente.")
            except ValueError:
                tkmsg.showerror("Error", "Debes ingresar valores numéricos en ambos campos.")
            except Exception as e:
                tkmsg.showerror("Error", f"Error al guardar: {e}")

        ctk.CTkButton(scroll_frame, text="Guardar", command=guardar_config).pack(pady=8)
        ctk.CTkButton(scroll_frame, text="Atrás", command=mostrar_lista_ids).pack(pady=8)

    mostrar_lista_ids()
    app.mainloop()

def draw_scenery(screen):
    """Dibuja el fondo, río, líneas de carril y árboles."""
    screen.fill(GRASS_COLOR)
    # Río
    pygame.draw.rect(screen, RIVER_COLOR, (BRIDGE_START_X, 0, BRIDGE_END_X - BRIDGE_START_X, SCREEN_HEIGHT))
    # Carretera
    pygame.draw.rect(screen, ROAD_COLOR, (0, BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 2, SIM_WIDTH, BRIDGE_HEIGHT))
    pygame.draw.rect(screen, GRAY, (BRIDGE_START_X, BRIDGE_Y_CENTER - 2, BRIDGE_END_X - BRIDGE_START_X, 4)) # Puente
    # Líneas de carril
    for x in range(LANE_LINE_GAP, BRIDGE_START_X - LANE_LINE_WIDTH, LANE_LINE_WIDTH + LANE_LINE_GAP):
        pygame.draw.rect(screen, WHITE, (x, BRIDGE_Y_CENTER - LANE_LINE_HEIGHT / 2, LANE_LINE_WIDTH, LANE_LINE_HEIGHT))
    for x in range(BRIDGE_END_X + LANE_LINE_GAP, SIM_WIDTH - LANE_LINE_WIDTH, LANE_LINE_WIDTH + LANE_LINE_GAP):
        pygame.draw.rect(screen, WHITE, (x, BRIDGE_Y_CENTER - LANE_LINE_HEIGHT / 2, LANE_LINE_WIDTH, LANE_LINE_HEIGHT))
    # Árboles (simples círculos y rectángulos)
    pygame.draw.rect(screen, (139, 69, 19), (100, 100, 20, 40)); pygame.draw.circle(screen, (0, 100, 0), (110, 80), 30)
    pygame.draw.rect(screen, (139, 69, 19), (800, 450, 20, 40)); pygame.draw.circle(screen, (0, 100, 0), (810, 430), 30)
    pygame.draw.rect(screen, (139, 69, 19), (50, 500, 20, 40)); pygame.draw.circle(screen, (0, 120, 0), (60, 480), 30)

def draw_traffic_lights(screen, status):
    """Dibuja los semáforos en los extremos del puente."""
    light_status = status.get('traffic_light', 'NONE')
    # Semáforo Norte (izquierda)
    north_light_color = GREEN_LIGHT if light_status == 'NORTH' else RED_LIGHT
    pygame.draw.circle(screen, north_light_color, (BRIDGE_START_X - 25, BRIDGE_Y_CENTER - 20), 10)
    # Semáforo Sur (derecha)
    south_light_color = GREEN_LIGHT if light_status == 'SOUTH' else RED_LIGHT
    pygame.draw.circle(screen, south_light_color, (BRIDGE_END_X + 25, BRIDGE_Y_CENTER + 20), 10)

def draw_stats_panel(screen, status, log, fonts):
    """Dibuja el panel de estadísticas en el lado derecho con log responsivo."""
    panel_rect = pygame.Rect(SIM_WIDTH, 0, PANEL_WIDTH, SCREEN_HEIGHT)
    pygame.draw.rect(screen, PANEL_BG_COLOR, panel_rect)
    
    y_pos = 20
    # Título
    title = fonts['title'].render("Panel de Control", True, WHITE)
    screen.blit(title, (SIM_WIDTH + (PANEL_WIDTH - title.get_width()) / 2, y_pos)); y_pos += 40
    
    # Estado del Puente
    status_text = status.get('bridge_status', 'DESCONOCIDO')
    status_color = (100, 255, 100) if status_text == 'LIBRE' else (255, 150, 50)
    text_surf = fonts['large'].render(f"Puente: {status_text}", True, status_color)
    screen.blit(text_surf, (SIM_WIDTH + 20, y_pos)); y_pos += 35
    
    # Dirección
    direction_text = status.get('current_direction') or "N/A"
    text_surf = fonts['medium'].render(f"Dirección: {direction_text}", True, WHITE)
    screen.blit(text_surf, (SIM_WIDTH + 20, y_pos)); y_pos += 45
    
    # Cola Norte
    waiting_n = status.get('waiting_north', 0)
    text_surf = fonts['medium'].render(f"Esperando en Norte: {waiting_n}", True, WHITE)
    screen.blit(text_surf, (SIM_WIDTH + 20, y_pos)); y_pos += 25
    pygame.draw.rect(screen, PROGRESS_BAR_BG, (SIM_WIDTH + 20, y_pos, PANEL_WIDTH - 40, 10))
    if waiting_n > 0: pygame.draw.rect(screen, PROGRESS_BAR_FG, (SIM_WIDTH + 20, y_pos, min(PANEL_WIDTH-40, waiting_n * 20), 10))
    y_pos += 35

    # Cola Sur
    waiting_s = status.get('waiting_south', 0)
    text_surf = fonts['medium'].render(f"Esperando en Sur: {waiting_s}", True, WHITE)
    screen.blit(text_surf, (SIM_WIDTH + 20, y_pos)); y_pos += 25
    pygame.draw.rect(screen, PROGRESS_BAR_BG, (SIM_WIDTH + 20, y_pos, PANEL_WIDTH - 40, 10))
    if waiting_s > 0: pygame.draw.rect(screen, PROGRESS_BAR_FG, (SIM_WIDTH + 20, y_pos, min(PANEL_WIDTH-40, waiting_s * 20), 10))
    y_pos += 45
    
    # Log de Eventos responsivo
    log_title = fonts['large'].render("Registro de Eventos", True, WHITE)
    screen.blit(log_title, (SIM_WIDTH + 20, y_pos)); y_pos += 30

    max_log_width = PANEL_WIDTH - 40
    for entry in log:
        # Wrap manual usando el ancho máximo y el font
        wrapped_lines = []
        words = entry.split(' ')
        line = ""
        for word in words:
            test_line = line + (" " if line else "") + word
            test_surf = fonts['small'].render(test_line, True, GRAY)
            if test_surf.get_width() > max_log_width and line:
                wrapped_lines.append(line)
                line = word
            else:
                line = test_line
        if line:
            wrapped_lines.append(line)
        for wline in wrapped_lines:
            log_surf = fonts['small'].render(wline, True, GRAY)
            screen.blit(log_surf, (SIM_WIDTH + 20, y_pos))
            y_pos += 20


def main():
    pygame.init()
    ctk.set_appearance_mode("system")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simulador del Puente de Una Vía - Interfaz Unificada")
    clock = pygame.time.Clock()
    fonts = {
        'car_id': pygame.font.SysFont("Arial", 10, bold=True),
        'button': pygame.font.SysFont("Arial", 16),
        'title': pygame.font.SysFont("Arial", 24, bold=True),
        'large': pygame.font.SysFont("Arial", 18, bold=True),
        'medium': pygame.font.SysFont("Arial", 16),
        'small': pygame.font.SysFont("Consolas", 12),
    }

    # --- Inicializar y reproducir música solo una vez ---
    pygame.mixer.init()
    try:
        pygame.mixer.music.load("assets/Undertale.mp3")
        pygame.mixer.music.play(-1)  # Repetir indefinidamente
    except Exception as e:
        print(f"Error al reproducir música: {e}")

    # Iniciar hilo para escuchar al servidor
    network_thread = threading.Thread(target=listen_for_server_updates, daemon=True); network_thread.start()

    carros = []
    num_carros = random.randint(1, 7)
    for i in range(num_carros):
        carro = Carro(i + 1, random.choice(["NORTH", "SOUTH"]), random.uniform(2, 4), random.uniform(4, 10))
        carros.append(carro)
        thread = threading.Thread(target=carro_lifecycle, args=(carro,), daemon=True); thread.start()

    add_button_rect = pygame.Rect(SIM_WIDTH - 160, 10, 150, 40)
    modify_button_rect = pygame.Rect(SIM_WIDTH - 160, 60, 150, 40)

    ADD_BTN_COLOR = BUTTON_COLOR
    ADD_BTN_HOVER = (130, 130, 255)
    MODIFY_BTN_COLOR = BUTTON_COLOR
    MODIFY_BTN_HOVER = (130, 180, 255)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        mouse_over_add = add_button_rect.collidepoint(mouse_pos)
        mouse_over_modify = modify_button_rect.collidepoint(mouse_pos)

        # Cambiar cursor si está sobre los botones
        if mouse_over_add or mouse_over_modify:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        else:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if add_button_rect.collidepoint(event.pos):
                    form_thread = threading.Thread(target=abrir_formulario_agregar_carro, args=(carros, carros_lock), daemon=True)
                    form_thread.start()
                if modify_button_rect.collidepoint(event.pos):
                    form_thread = threading.Thread(target=abrir_formulario_modificar_carro, args=(carros, carros_lock), daemon=True)
                    form_thread.start()

        # --- Lógica de Dibujo ---
        draw_scenery(screen)
        
        # Obtener una copia segura del estado para dibujar
        with status_lock:
            status_copy = current_server_status.copy()
            log_copy = list(event_log)
        
        draw_traffic_lights(screen, status_copy)
        draw_stats_panel(screen, status_copy, log_copy, fonts)

        # Dibujar botón "Agregar" con hover
        pygame.draw.rect(screen, ADD_BTN_HOVER if mouse_over_add else ADD_BTN_COLOR, add_button_rect)
        add_text = fonts['button'].render("Agregar Carro", True, BUTTON_TEXT_COLOR)
        screen.blit(add_text, (add_button_rect.x + (add_button_rect.width - add_text.get_width()) / 2, 
                               add_button_rect.y + (add_button_rect.height - add_text.get_height()) / 2))

        # Dibujar botón "Modificar" con hover
        pygame.draw.rect(screen, MODIFY_BTN_HOVER if mouse_over_modify else MODIFY_BTN_COLOR, modify_button_rect)
        modify_text = fonts['button'].render("Modificar", True, BUTTON_TEXT_COLOR)
        screen.blit(modify_text, (modify_button_rect.x + (modify_button_rect.width - modify_text.get_width()) / 2,
                                  modify_button_rect.y + (modify_button_rect.height - modify_text.get_height()) / 2))

        with carros_lock:
            for carro in list(carros):
                # Evitar que los vehículos se dibujen sobre el panel lateral
                if carro.rect.right <= SIM_WIDTH:
                    carro.update(carros)
                    carro.draw(screen, fonts['car_id'])
                else:
                    # Si el carro está fuera del área de simulación, no lo dibujes
                    carro.update(carros)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()