import pygame
import socket
import threading
import random
import sys
import time
import customtkinter as ctk

# --- Constantes de Configuración de Pygame ---
SCREEN_WIDTH, SCREEN_HEIGHT = 900, 600
BRIDGE_Y_CENTER = SCREEN_HEIGHT / 2
BRIDGE_HEIGHT = 80 # Puente más ancho para dos carriles de espera
BRIDGE_START_X, BRIDGE_END_X = 200, 700
CAR_WIDTH, CAR_HEIGHT = 30, 20
FPS = 60

# --- Nuevas Constantes para Colisiones ---
SAFE_DISTANCE_ON_BRIDGE = 25 # Distancia segura entre carros en el puente
QUEUE_GAP = 10 # Espacio entre carros en la cola de espera

# --- Colores ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
ROAD_COLOR = (50, 50, 50)
GRASS_COLOR = (34, 139, 34)
BUTTON_COLOR = (100, 100, 200)
BUTTON_TEXT_COLOR = WHITE

# --- Thread-safety para la lista de carros ---
# Es crucial para poder añadir carros de forma dinámica desde otro hilo (el del formulario)
carros_lock = threading.Lock()

class Carro:
    """Representa un único carro en la simulación con lógica de colisión."""
    def __init__(self, car_id, direction, speed, delay_time):
        self.id = car_id
        self.direction = direction
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        
        # --- Parámetros personalizables ---
        self.original_speed = speed
        self.delay_time = delay_time
        self.speed = self.original_speed

        # Posiciones
        y_pos = (BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 4 - CAR_HEIGHT) if direction == 'NORTH' else (BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 4)
        self.original_y = y_pos # Guardamos la Y original para el retorno

        self.start_pos_x = -CAR_WIDTH if direction == 'NORTH' else SCREEN_WIDTH

        self.rect = pygame.Rect(self.start_pos_x, self.original_y, CAR_WIDTH, CAR_HEIGHT)

        self.state = 'IDLE' # IDLE, DRIVING_TO_BRIDGE, WAITING, CROSSING, RETURNING
        self.status_text = "Iniciando..."

    def reset_position_and_direction(self):
        # Alternar dirección y ajustar posiciones
        if self.direction == 'NORTH':
            self.direction = 'SOUTH'
            self.original_y = BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 4
            self.start_pos_x = SCREEN_WIDTH
        else:
            self.direction = 'NORTH'
            self.original_y = BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 4 - CAR_HEIGHT
            self.start_pos_x = -CAR_WIDTH
        self.rect.x = self.start_pos_x
        self.rect.y = self.original_y

    def update(self, all_cars):
        """Mueve el carro basado en su estado y evita colisiones."""
        
        # Lógica para reanudar la velocidad si el camino está libre
        self.speed = self.original_speed

        if self.state == 'DRIVING_TO_BRIDGE' or self.state == 'WAITING':
            # --- Lógica de la cola de espera ---
            # Encontrar el carro que está justo delante en la cola
            front_car = None
            min_dist = float('inf')

            for other in all_cars:
                if other.id != self.id and other.direction == self.direction and (other.state == 'WAITING' or other.state == 'DRIVING_TO_BRIDGE'):
                    if self.direction == 'NORTH':
                        if self.rect.x < other.rect.x:
                            dist = other.rect.x - self.rect.x
                            if dist < min_dist:
                                min_dist = dist
                                front_car = other
                    else: # SOUTH
                        if self.rect.x > other.rect.x:
                            dist = self.rect.x - other.rect.x
                            if dist < min_dist:
                                min_dist = dist
                                front_car = other
            
            target_x = 0
            if self.direction == 'NORTH':
                target_x = (front_car.rect.left - QUEUE_GAP - CAR_WIDTH) if front_car else (BRIDGE_START_X - 20 - CAR_WIDTH)
                if self.rect.x < target_x:
                    self.rect.x += self.speed
                else:
                    self.rect.x = target_x 
                    if self.state == 'DRIVING_TO_BRIDGE': self.state = 'WAITING'
            else: # SOUTH
                target_x = (front_car.rect.right + QUEUE_GAP) if front_car else (BRIDGE_END_X + 20)
                if self.rect.x > target_x:
                    self.rect.x -= self.speed
                else:
                    self.rect.x = target_x 
                    if self.state == 'DRIVING_TO_BRIDGE': self.state = 'WAITING'

        elif self.state == 'CROSSING':
            self.rect.y = BRIDGE_Y_CENTER - CAR_HEIGHT / 2 
            
            for other in all_cars:
                if other.id != self.id and other.direction == self.direction and other.state == 'CROSSING':
                    if self.direction == 'NORTH':
                        if other.rect.x > self.rect.x and other.rect.x - self.rect.right < SAFE_DISTANCE_ON_BRIDGE:
                            self.speed = 0 
                            break
                    else: # SOUTH
                        if other.rect.x < self.rect.x and self.rect.left - other.rect.right < SAFE_DISTANCE_ON_BRIDGE:
                            self.speed = 0
                            break

            if self.direction == 'NORTH':
                if self.rect.x < BRIDGE_END_X: self.rect.x += self.speed
                else: self.state = 'RETURNING'
            else: # SOUTH
                if self.rect.right > BRIDGE_START_X: self.rect.x -= self.speed
                else: self.state = 'RETURNING'

        elif self.state == 'RETURNING':
            self.rect.y = self.original_y
            
            if self.direction == 'NORTH':
                if self.rect.x < SCREEN_WIDTH + CAR_WIDTH: self.rect.x += self.speed
                else: self.state = 'IDLE'
            else: # SOUTH
                if self.rect.right > -CAR_WIDTH: self.rect.x -= self.speed
                else: self.state = 'IDLE'

    def draw(self, screen, font):
        pygame.draw.rect(screen, self.color, self.rect)
        id_render = font.render(str(self.id), True, BLACK)
        screen.blit(id_render, (self.rect.centerx - id_render.get_width() / 2, self.rect.centery - id_render.get_height() / 2))


def carro_lifecycle(carro: Carro):
    """El ciclo de vida y la lógica de red para un único carro."""
    HOST = '127.0.0.1'
    PORT = 65432

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
        except ConnectionRefusedError:
            carro.status_text = "Error: Servidor no encontrado."
            carro.state = 'ERROR'
            return

        while True:
            carro.status_text = "Descansando"
            carro.state = 'IDLE'
            carro.rect.x = carro.start_pos_x
            carro.rect.y = carro.original_y
            carro.speed = carro.original_speed
            
            # Utiliza el tiempo de descanso personalizado del carro
            time.sleep(carro.delay_time)

            carro.status_text = f"Yendo al puente desde el {carro.direction}"
            carro.state = 'DRIVING_TO_BRIDGE'
            while carro.state == 'DRIVING_TO_BRIDGE': time.sleep(0.1)

            carro.status_text = "Esperando permiso"
            carro.state = 'WAITING'
            s.sendall(f"REQUEST_CROSS {carro.direction}\n".encode('utf-8'))
            
            buffer = ""
            while True:
                try:
                    data = s.recv(1024).decode('utf-8')
                    if not data:
                        carro.state = 'ERROR'; return
                    if 'GRANT_CROSS' in data:
                        break
                except (ConnectionAbortedError, ConnectionResetError):
                    carro.state = 'ERROR'; return

            carro.status_text = "¡Cruzando!"
            carro.state = 'CROSSING'
            while carro.state == 'CROSSING': time.sleep(0.1)

            carro.status_text = "Cruce completado"
            s.sendall("RELEASE_BRIDGE\n".encode('utf-8'))
            
            while carro.state == 'RETURNING': time.sleep(0.1)

            carro.reset_position_and_direction()

def abrir_formulario_agregar_carro(lista_carros):
    """
    Abre una ventana de customtkinter para que el usuario ingrese los datos de un nuevo carro.
    """
    app = ctk.CTk()
    app.title("Agregar Nuevo Carro")
    app.geometry("350x450")
    
    frame = ctk.CTkFrame(app)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    ctk.CTkLabel(frame, text="ID del Carro (número único):").pack(pady=5)
    id_entry = ctk.CTkEntry(frame)
    id_entry.pack()

    ctk.CTkLabel(frame, text="Velocidad (ej. 2.5):").pack(pady=5)
    speed_entry = ctk.CTkEntry(frame)
    speed_entry.insert(0, "2.5")
    speed_entry.pack()

    ctk.CTkLabel(frame, text="Tiempo de Descanso (segundos):").pack(pady=5)
    delay_entry = ctk.CTkEntry(frame)
    delay_entry.insert(0, "5.0")
    delay_entry.pack()

    ctk.CTkLabel(frame, text="Dirección Inicial:").pack(pady=5)
    direction_var = ctk.StringVar(value="NORTH")
    direction_menu = ctk.CTkOptionMenu(frame, values=["NORTH", "SOUTH"], variable=direction_var)
    direction_menu.pack()

    error_label = ctk.CTkLabel(frame, text="", text_color="red")
    error_label.pack(pady=5)

    def procesar_nuevo_carro():
        try:
            car_id = int(id_entry.get())
            speed = float(speed_entry.get())
            delay = float(delay_entry.get())
            direction = direction_var.get()

            with carros_lock:
                id_en_uso = any(c.id == car_id for c in lista_carros)

            if id_en_uso:
                error_label.configure(text=f"Error: El ID de carro '{car_id}' ya está en uso.")
                return
            
            if speed <= 0 or delay <= 0:
                error_label.configure(text="Error: Velocidad y descanso deben ser > 0.")
                return

            # Si la validación es correcta, creamos el carro
            nuevo_carro = Carro(car_id=car_id, direction=direction, speed=speed, delay_time=delay)
            
            with carros_lock:
                lista_carros.append(nuevo_carro)
            
            thread = threading.Thread(target=carro_lifecycle, args=(nuevo_carro,), daemon=True)
            thread.start()

            app.destroy() # Cierra el formulario

        except ValueError:
            error_label.configure(text="Error: ID, velocidad y descanso deben ser números válidos.")
        except Exception as e:
            error_label.configure(text=f"Error inesperado: {e}")

    confirm_button = ctk.CTkButton(app, text="Confirmar", command=procesar_nuevo_carro)
    confirm_button.pack(pady=10)

    app.mainloop()

def main():
    pygame.init()
    ctk.set_appearance_mode("system") # O "dark", "light"

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simulador del Puente de Una Vía - Con Lógica de Colisión")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 10, bold=True)
    label_font = pygame.font.SysFont("Arial", 24, bold=True)
    button_font = pygame.font.SysFont("Arial", 16)
    
    carros = []
    num_carros_iniciales = 5
    
    for i in range(num_carros_iniciales):
        direction = random.choice(["NORTH", "SOUTH"])
        speed = random.uniform(2, 4)
        delay = random.uniform(4, 10)
        carro = Carro(i + 1, direction, speed, delay)
        carros.append(carro)
        thread = threading.Thread(target=carro_lifecycle, args=(carro,), daemon=True)
        thread.start()

    # --- Configuración del Botón "Agregar" en Pygame ---
    add_button_rect = pygame.Rect(SCREEN_WIDTH - 160, 10, 150, 40)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if add_button_rect.collidepoint(event.pos):
                    # Lanzar el formulario en un nuevo hilo para no bloquear Pygame
                    form_thread = threading.Thread(target=abrir_formulario_agregar_carro, args=(carros,), daemon=True)
                    form_thread.start()


        # --- Lógica de Dibujo ---
        screen.fill(GRASS_COLOR)
        pygame.draw.rect(screen, ROAD_COLOR, (0, BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 2, SCREEN_WIDTH, BRIDGE_HEIGHT))
        pygame.draw.rect(screen, GRAY, (BRIDGE_START_X, BRIDGE_Y_CENTER - 2, BRIDGE_END_X - BRIDGE_START_X, 4))
        
        north_label = label_font.render("NORTH", True, (0, 0, 200))
        south_label = label_font.render("SOUTH", True, (200, 0, 0))
        screen.blit(north_label, (BRIDGE_START_X - north_label.get_width() - 20, BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 2 - 30))
        screen.blit(south_label, (BRIDGE_END_X + 20, BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 2 + 10))

        # Dibujar el botón "Agregar"
        pygame.draw.rect(screen, BUTTON_COLOR, add_button_rect)
        add_text = button_font.render("Agregar Carro", True, BUTTON_TEXT_COLOR)
        screen.blit(add_text, (add_button_rect.x + (add_button_rect.width - add_text.get_width()) / 2, 
                               add_button_rect.y + (add_button_rect.height - add_text.get_height()) / 2))

        # Acceso seguro a la lista de carros para actualizar y dibujar
        with carros_lock:
            # Creamos una copia de la lista para iterar, previene problemas si un carro se elimina
            for carro in list(carros):
                carro.update(carros)
                carro.draw(screen, font)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()