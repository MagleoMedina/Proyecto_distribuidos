import pygame
import socket
import threading
import random
import sys
import time

# --- Constantes de Configuración de Pygame ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 300
BRIDGE_Y = 130
BRIDGE_HEIGHT = 40
BRIDGE_START_X, BRIDGE_END_X = 150, 650
CAR_WIDTH, CAR_HEIGHT = 30, 20
FPS = 60

# --- Colores ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
ROAD_COLOR = (50, 50, 50)

class Car:
    def __init__(self, direction):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"Carro Cliente - Dirección {direction}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 18)

        self.direction = direction
        self.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        self.speed = random.uniform(2, 4)
        
        self.start_pos_x = -CAR_WIDTH if direction == 'NORTH' else SCREEN_WIDTH
        self.wait_pos_x = BRIDGE_START_X - CAR_WIDTH - 20 if direction == 'NORTH' else BRIDGE_END_X + 20
        self.rect = pygame.Rect(self.start_pos_x, BRIDGE_Y + (BRIDGE_HEIGHT - CAR_HEIGHT) / 2, CAR_WIDTH, CAR_HEIGHT)

        self.state = 'IDLE' # Estados: IDLE, DRIVING_TO_BRIDGE, WAITING, CROSSING, RETURNING
        self.status_text = "Iniciando..."
        
        self.lifecycle_thread = threading.Thread(target=self.car_lifecycle, daemon=True)
        self.lifecycle_thread.start()

    def draw_environment(self):
        self.screen.fill(WHITE)
        pygame.draw.rect(self.screen, ROAD_COLOR, (0, BRIDGE_Y, SCREEN_WIDTH, BRIDGE_HEIGHT))
        pygame.draw.rect(self.screen, GRAY, (BRIDGE_START_X, BRIDGE_Y, BRIDGE_END_X - BRIDGE_START_X, BRIDGE_HEIGHT), 3)
        status_render = self.font.render(self.status_text, True, BLACK)
        self.screen.blit(status_render, (10, 10))

    def update_position(self):
        if self.state == 'DRIVING_TO_BRIDGE':
            if self.direction == 'NORTH':
                self.rect.x += self.speed
                if self.rect.x >= self.wait_pos_x:
                    self.rect.x = self.wait_pos_x
                    self.state = 'WAITING'
            else: # SOUTH
                self.rect.x -= self.speed
                if self.rect.x <= self.wait_pos_x:
                    self.rect.x = self.wait_pos_x
                    self.state = 'WAITING'
        
        elif self.state == 'CROSSING':
            if self.direction == 'NORTH':
                self.rect.x += self.speed
                if self.rect.x > BRIDGE_END_X:
                    self.state = 'RETURNING'
            else: # SOUTH
                self.rect.x -= self.speed
                if self.rect.right < BRIDGE_START_X:
                    self.state = 'RETURNING'

        elif self.state == 'RETURNING':
            if self.direction == 'NORTH':
                self.rect.x += self.speed
                if self.rect.x > SCREEN_WIDTH:
                    self.state = 'IDLE' # Fin del ciclo visual
            else: # SOUTH
                self.rect.x -= self.speed
                if self.rect.right < 0:
                    self.state = 'IDLE' # Fin del ciclo visual

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            self.update_position()
            self.draw_environment()
            pygame.draw.rect(self.screen, self.color, self.rect)
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

    def car_lifecycle(self):
        HOST = '127.0.0.1'
        PORT = 65432
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((HOST, PORT))
            except ConnectionRefusedError:
                self.status_text = "Error: Servidor no encontrado."
                self.state = 'ERROR'
                return

            while True:
                # 1. Descansar
                self.status_text = "Descansando..."
                self.state = 'IDLE'
                self.rect.x = self.start_pos_x # Reiniciar posición visual
                time.sleep(random.uniform(3, 8))

                # 2. Conducir hasta el puente
                self.status_text = f"Yendo al puente desde el {self.direction}"
                self.state = 'DRIVING_TO_BRIDGE'
                while self.state == 'DRIVING_TO_BRIDGE':
                    time.sleep(0.1) # Esperar a que el hilo principal mueva el carro

                # 3. Solicitar cruce y esperar
                self.status_text = "Esperando permiso para cruzar..."
                s.sendall(f"REQUEST_CROSS {self.direction}\n".encode('utf-8'))
                
                # Bucle de espera para el permiso
                buffer = ""
                while True:
                    try:
                        data = s.recv(1024).decode('utf-8')
                        if not data:
                            self.state = 'ERROR'
                            self.status_text = 'Servidor desconectado.'
                            return
                        buffer += data
                        if '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            if line.strip() == 'GRANT_CROSS':
                                break # Permiso recibido, salir del bucle de espera
                    except ConnectionAbortedError:
                        self.state = 'ERROR'
                        self.status_text = 'Conexión cerrada por el servidor.'
                        return


                # 4. Cruzar
                self.status_text = "¡Cruzando el puente!"
                self.state = 'CROSSING'
                while self.state == 'CROSSING':
                    time.sleep(0.1)

                # 5. Liberar el puente
                self.status_text = "Cruce completado."
                s.sendall("RELEASE_BRIDGE\n".encode('utf-8'))
                
                # El ciclo se reiniciará después del descanso

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].upper() not in ["NORTH", "SOUTH"]:
        print("Uso: python cliente_carro.py <NORTH|SOUTH>")
        sys.exit(1)
        
    car_direction = sys.argv[1].upper()
    car_client = Car(car_direction)
    car_client.run()