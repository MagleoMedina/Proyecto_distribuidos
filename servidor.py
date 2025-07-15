import socket
import threading
import json
import time
from collections import deque

# --- Estado Compartido del Puente ---
bridge_lock = threading.RLock()
puente_ocupado = False
direccion_actual = None
cola_espera = {"NORTH": [], "SOUTH": []}
clientes_conectados = []
coches_en_puente = 0
carros_cruzando = []
event_log = deque(maxlen=10) 

def log_event(text):
    """Añade un evento al log con marca de tiempo."""
    timestamp = time.strftime("%H:%M:%S")
    event_log.append(f"[{timestamp}] {text}")
    notificar_a_todos()

def notificar_a_todos():
    """Envía el estado actual completo, incluyendo logs y semáforos, a todos los clientes."""
    with bridge_lock:
        light_status = "NONE"
        if puente_ocupado:
            light_status = direccion_actual
        
        estado = {
            "bridge_status": "OCUPADO" if puente_ocupado else "LIBRE",
            "current_direction": direccion_actual,
            "waiting_north": len(cola_espera["NORTH"]),
            "waiting_south": len(cola_espera["SOUTH"]),
            "crossing_cars": carros_cruzando[:],
            "traffic_light": light_status,
            "log": list(event_log)
        }
        mensaje = f"STATUS_UPDATE {json.dumps(estado)}\n"
        for cliente_socket in clientes_conectados:
            try:
                cliente_socket.sendall(mensaje.encode('utf-8'))
            except socket.error:
                continue

def gestionar_siguiente_carro():
    """Lógica justa para decidir qué carro cruza a continuación."""
    global puente_ocupado, direccion_actual, coches_en_puente, carros_cruzando
    with bridge_lock:
        if direccion_actual == "NORTH":
            direcciones_a_chequear = ["SOUTH", "NORTH"]
        else:
            direcciones_a_chequear = ["NORTH", "SOUTH"]

        for dir in direcciones_a_chequear:
            if len(cola_espera[dir]) > 0:
                cliente_socket, client_address, car_id = cola_espera[dir].pop(0)
                puente_ocupado = True
                direccion_actual = dir
                coches_en_puente = 1
                carros_cruzando = [car_id]
                log_event(f"Servidor: Permiso a Carro {car_id} ({dir})")
                try:
                    cliente_socket.send("GRANT_CROSS\n".encode('utf-8'))
                except (socket.error, BrokenPipeError):
                    log_event(f"Error: Cliente {car_id} desconectado.")
                    coches_en_puente = 0
                    carros_cruzando = []
                    gestionar_siguiente_carro()
                notificar_a_todos()
                return

        # Si no hay nadie esperando, el puente queda libre
        puente_ocupado = False
        direccion_actual = None
        coches_en_puente = 0
        carros_cruzando = []
        log_event("Servidor: Puente libre y sin colas.")
        notificar_a_todos()

def handle_client(client_socket, client_address):
    global puente_ocupado, direccion_actual, coches_en_puente, carros_cruzando
    print(f"[NUEVA CONEXIÓN] {client_address} conectado.")
    with bridge_lock:
        clientes_conectados.append(client_socket)
    
    notificar_a_todos() # Enviar estado inicial

    try:
        while True:
            mensaje = client_socket.recv(1024).decode('utf-8').strip()
            if not mensaje: break

            partes = mensaje.split()
            comando = partes[0]

            if comando == "REQUEST_CROSS":
                direccion = partes[1]
                car_id = int(partes[2])
                with bridge_lock:
                    log_event(f"Cliente: Carro {car_id} solicita cruce ({direccion})")
                    opuesta = "NORTH" if direccion == "SOUTH" else "SOUTH"
                    
                    if not puente_ocupado or (direccion_actual == direccion and len(cola_espera[opuesta]) == 0):
                        puente_ocupado = True
                        direccion_actual = direccion
                        coches_en_puente += 1
                        if car_id not in carros_cruzando:
                            carros_cruzando.append(car_id)
                        log_event(f"Servidor: Permiso inmediato a Carro {car_id}")
                        try:
                            client_socket.send("GRANT_CROSS\n".encode('utf-8'))
                        except socket.error:
                            coches_en_puente -= 1
                            if car_id in carros_cruzando: carros_cruzando.remove(car_id)
                    else:
                        log_event(f"Servidor: Encolado Carro {car_id} ({direccion})")
                        cola_espera[direccion].append((client_socket, client_address, car_id))
                notificar_a_todos()

            elif comando == "RELEASE_BRIDGE":
                car_id_released = -1
                with bridge_lock:

                    if carros_cruzando: car_id_released = carros_cruzando[0]

                    coches_en_puente -= 1
                    if car_id_released != -1 and car_id_released in carros_cruzando:
                        carros_cruzando.remove(car_id_released)
                    
                    log_event(f"Cliente: Carro liberó el puente. Restantes: {coches_en_puente}")
                    if coches_en_puente <= 0:
                        coches_en_puente = 0
                        gestionar_siguiente_carro()
                notificar_a_todos()

    except (ConnectionResetError, BrokenPipeError):
        print(f"[DESCONEXIÓN] {client_address} se desconectó.")
    finally:
        with bridge_lock:
            if client_socket in clientes_conectados:
                clientes_conectados.remove(client_socket)
            for dir in cola_espera:
                cola_espera[dir] = [(s, a, cid) for s, a, cid in cola_espera[dir] if s != client_socket]
        client_socket.close()
        log_event(f"Sistema: Cliente {client_address} desconectado.")

def main():
    HOST = '127.0.0.1'
    PORT = 65432
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[ESCUCHANDO] El servidor está escuchando en {HOST}:{PORT}")
    log_event("Servidor iniciado y escuchando.")

    while True:
        client_socket, client_address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    main()