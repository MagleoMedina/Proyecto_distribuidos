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

# --- Colores ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
ROAD_COLOR = (50, 50, 50)
GRASS_COLOR = (34, 139, 34)

class Carro:
    """Representa un único carro en la simulación (sin lógica de red)."""
    def __init__(self, car_id, direction, y_offset):
        self.id = car_id
        self.direction = direction
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        self.speed = random.uniform(2, 4)
        
        # Posiciones
        y_pos = (BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 4 - CAR_HEIGHT) if direction == 'NORTH' else (BRIDGE_Y_CENTER + BRIDGE_HEIGHT / 4)
        self.start_pos_x = -CAR_WIDTH if direction == 'NORTH' else SCREEN_WIDTH
        self.wait_pos_x = (BRIDGE_START_X - CAR_WIDTH - 20 - y_offset) if direction == 'NORTH' else (BRIDGE_END_X + 20 + y_offset)
        self.rect = pygame.Rect(self.start_pos_x, y_pos, CAR_WIDTH, CAR_HEIGHT)

        # Estado controlado por el hilo de red
        self.state = 'IDLE' # IDLE, DRIVING_TO_BRIDGE, WAITING, CROSSING, RETURNING
        self.status_text = "Iniciando..."

    def update(self):
        """Mueve el carro basado en su estado actual."""
        if self.state == 'DRIVING_TO_BRIDGE':
            if self.direction == 'NORTH':
                if self.rect.x < self.wait_pos_x: self.rect.x += self.speed
                else: self.state = 'WAITING'
            else: # SOUTH
                if self.rect.x > self.wait_pos_x: self.rect.x -= self.speed
                else: self.state = 'WAITING'
        
        elif self.state == 'CROSSING':
            # La posición Y se ajusta para que cruce por el centro
            self.rect.y = BRIDGE_Y_CENTER - CAR_HEIGHT / 2
            if self.direction == 'NORTH':
                if self.rect.x < BRIDGE_END_X: self.rect.x += self.speed
                else: self.state = 'RETURNING'
            else: # SOUTH
                if self.rect.right > BRIDGE_START_X: self.rect.x -= self.speed
                else: self.state = 'RETURNING'

        elif self.state == 'RETURNING':
            if self.direction == 'NORTH':
                if self.rect.x < SCREEN_WIDTH: self.rect.x += self.speed
                else: self.state = 'IDLE'
            else: # SOUTH
                if self.rect.right > 0: self.rect.x -= self.speed
                else: self.state = 'IDLE'

    def draw(self, screen, font):
        """Dibuja el carro y su ID."""
        pygame.draw.rect(screen, self.color, self.rect)
        id_render = font.render(str(self.id), True, WHITE)
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
            # 1. Descansar
            carro.status_text = "Descansando"
            carro.state = 'IDLE'
            # Reiniciar posición visual
            y_pos_original = carro.rect.y
            carro.rect.x = carro.start_pos_x
            carro.rect.y = y_pos_original
            time.sleep(random.uniform(4, 10))

            # 2. Conducir hasta el puente
            carro.status_text = f"Yendo al puente desde el {carro.direction}"
            carro.state = 'DRIVING_TO_BRIDGE'
            while carro.state == 'DRIVING_TO_BRIDGE': time.sleep(0.1)

            # 3. Solicitar cruce y esperar
            carro.status_text = "Esperando permiso"
            s.sendall(f"REQUEST_CROSS {carro.direction}\n".encode('utf-8'))
            
            buffer = ""
            while True:
                try:
                    data = s.recv(1024).decode('utf-8')
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
    pygame.display.set_caption("Simulador del Puente de Una Vía")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 12, bold=True)
    
    carros = []
    num_carros = random.randint(6, 12)
    
    # Contadores para el offset de espera
    north_offset_count = 0
    south_offset_count = 0

    for i in range(num_carros):
        direction = random.choice(["NORTH", "SOUTH"])
        offset = 0
        if direction == "NORTH":
            offset = north_offset_count * (CAR_WIDTH + 5)
            north_offset_count += 1
        else:
            offset = south_offset_count * (CAR_WIDTH + 5)
            south_offset_count += 1

        carro = Carro(i + 1, direction, offset)
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
        pygame.draw.rect(screen, ROAD_COLOR, (0, BRIDGE_Y_CENTER - BRIDGE_HEIGHT / 2, SCREEN_WIDTH, BRIDGE_HEIGHT))
        pygame.draw.rect(screen, GRAY, (BRIDGE_START_X, BRIDGE_Y_CENTER - 1, BRIDGE_END_X - BRIDGE_START_X, 3))
        
        for carro in carros:
            carro.update()
            carro.draw(screen, font)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()