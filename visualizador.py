import pygame
import socket
import threading
import random
import sys
import time

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

class Carro:
    """Representa un único carro en la simulación con lógica de colisión."""
    def __init__(self, car_id, direction):
        self.id = car_id
        self.direction = direction
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        self.original_speed = random.uniform(2, 4)
        self.speed = self.original_speed
        
        # Posiciones
        y_pos = (BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 4 - CAR_HEIGHT) if direction == 'NORTH' else (BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 4)
        self.original_y = y_pos # Guardamos la Y original para el retorno
        
        self.start_pos_x = -CAR_WIDTH if direction == 'NORTH' else SCREEN_WIDTH
        
        # El 'wait_pos_x' ahora es dinámico y se calculará en el update
        self.rect = pygame.Rect(self.start_pos_x, self.original_y, CAR_WIDTH, CAR_HEIGHT)

        # Estado controlado por el hilo de red
        self.state = 'IDLE' # IDLE, DRIVING_TO_BRIDGE, WAITING, CROSSING, RETURNING
        self.status_text = "Iniciando..."

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
                        # Para NORTH, el carro de adelante tiene una X mayor
                        if self.rect.x < other.rect.x:
                            dist = other.rect.x - self.rect.x
                            if dist < min_dist:
                                min_dist = dist
                                front_car = other
                    else: # SOUTH
                        # Para SOUTH, el carro de adelante tiene una X menor
                        if self.rect.x > other.rect.x:
                            dist = self.rect.x - other.rect.x
                            if dist < min_dist:
                                min_dist = dist
                                front_car = other
            
            # Determinar la posición objetivo en la cola
            target_x = 0
            if self.direction == 'NORTH':
                target_x = (front_car.rect.left - QUEUE_GAP - CAR_WIDTH) if front_car else (BRIDGE_START_X - 20 - CAR_WIDTH)
                if self.rect.x < target_x:
                    self.rect.x += self.speed
                else:
                    self.rect.x = target_x # Ajuste final para no sobrepasar
                    if self.state == 'DRIVING_TO_BRIDGE': self.state = 'WAITING'
            else: # SOUTH
                target_x = (front_car.rect.right + QUEUE_GAP) if front_car else (BRIDGE_END_X + 20)
                if self.rect.x > target_x:
                    self.rect.x -= self.speed
                else:
                    self.rect.x = target_x # Ajuste final
                    if self.state == 'DRIVING_TO_BRIDGE': self.state = 'WAITING'

        elif self.state == 'CROSSING':
            # --- Lógica de colisión en el puente ---
            self.rect.y = BRIDGE_Y_CENTER - CAR_HEIGHT / 2 # Centrar en el carril de cruce
            
            for other in all_cars:
                if other.id != self.id and other.direction == self.direction and other.state == 'CROSSING':
                    if self.direction == 'NORTH':
                        # Si hay un carro adelante y está muy cerca, frena
                        if other.rect.x > self.rect.x and other.rect.x - self.rect.right < SAFE_DISTANCE_ON_BRIDGE:
                            self.speed = 0 # Detenerse
                            break
                    else: # SOUTH
                        # Si hay un carro adelante y está muy cerca, frena
                        if other.rect.x < self.rect.x and self.rect.left - other.rect.right < SAFE_DISTANCE_ON_BRIDGE:
                            self.speed = 0 # Detenerse
                            break

            # Mover el carro si no está frenado
            if self.direction == 'NORTH':
                if self.rect.x < BRIDGE_END_X: self.rect.x += self.speed
                else: self.state = 'RETURNING'
            else: # SOUTH
                if self.rect.right > BRIDGE_START_X: self.rect.x -= self.speed
                else: self.state = 'RETURNING'

        elif self.state == 'RETURNING':
            # --- Lógica de salida segura del puente ---
            # Moverse al carril de salida para no chocar con los que esperan
            self.rect.y = self.original_y
            
            if self.direction == 'NORTH':
                if self.rect.x < SCREEN_WIDTH + CAR_WIDTH: self.rect.x += self.speed
                else: self.state = 'IDLE' # El ciclo termina y esperará para empezar de nuevo
            else: # SOUTH
                if self.rect.right > -CAR_WIDTH: self.rect.x -= self.speed
                else: self.state = 'IDLE' # El ciclo termina

    def draw(self, screen, font):
        """Dibuja el carro y su ID."""
        pygame.draw.rect(screen, self.color, self.rect)
        id_render = font.render(str(self.id), True, BLACK) # Texto negro para mejor contraste
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
            # 1. Descansar (estado IDLE)
            carro.status_text = "Descansando"
            carro.state = 'IDLE'
            
            # Reiniciar posición visual fuera de la pantalla
            carro.rect.x = carro.start_pos_x
            carro.rect.y = carro.original_y
            carro.speed = carro.original_speed
            time.sleep(random.uniform(4, 10))

            # 2. Conducir hasta el puente
            carro.status_text = f"Yendo al puente desde el {carro.direction}"
            carro.state = 'DRIVING_TO_BRIDGE'
            while carro.state == 'DRIVING_TO_BRIDGE': time.sleep(0.1)

            # 3. Solicitar cruce y esperar
            carro.status_text = "Esperando permiso"
            carro.state = 'WAITING' # El estado cambia a WAITING visualmente mientras espera el permiso
            s.sendall(f"REQUEST_CROSS {carro.direction}\n".encode('utf-8'))
            
            buffer = ""
            while True:
                try:
                    data = s.recv(1024).decode('utf-8')
                    if not data:
                        carro.state = 'ERROR'; return
                    if 'GRANT_CROSS' in data:
                        break # Permiso recibido
                except (ConnectionAbortedError, ConnectionResetError):
                    carro.state = 'ERROR'; return

            # 4. Cruzar
            carro.status_text = "¡Cruzando!"
            carro.state = 'CROSSING'
            while carro.state == 'CROSSING': time.sleep(0.1)

            # 5. Liberar el puente
            carro.status_text = "Cruce completado"
            s.sendall("RELEASE_BRIDGE\n".encode('utf-8'))
            
            # El estado 'RETURNING' se activa automáticamente en el hilo principal
            while carro.state == 'RETURNING': time.sleep(0.1)

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simulador del Puente de Una Vía - Con Lógica de Colisión")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 10, bold=True)
    
    carros = []
    num_carros = random.randint(8, 15) # Aumentamos para ver mejor el efecto de cola
    
    for i in range(num_carros):
        direction = random.choice(["NORTH", "SOUTH"])
        # Ya no se necesita el offset en la creación
        carro = Carro(i + 1, direction)
        carros.append(carro)
        thread = threading.Thread(target=carro_lifecycle, args=(carro,), daemon=True)
        thread.start()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # --- Lógica de Dibujo ---
        screen.fill(GRASS_COLOR)
        # Dibujar carretera principal
        pygame.draw.rect(screen, ROAD_COLOR, (0, BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 2, SCREEN_WIDTH, BRIDGE_HEIGHT))
        # Dibujar puente (sólo la línea central para indicar la zona de cruce)
        pygame.draw.rect(screen, GRAY, (BRIDGE_START_X, BRIDGE_Y_CENTER - 2, BRIDGE_END_X - BRIDGE_START_X, 4))
        
        for carro in carros:
            # Pasamos la lista completa de carros para que cada uno pueda ver a los demás
            carro.update(carros)
            carro.draw(screen, font)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()