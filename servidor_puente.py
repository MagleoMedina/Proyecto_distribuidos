import socket
import threading
import json
import time

# --- Estado Compartido del Puente ---
# Esta sección debe ser segura para hilos (thread-safe)
#bridge_lock = threading.Lock()
bridge_lock = threading.RLock()
puente_ocupado = False
direccion_actual = None
cola_espera = {"NORTH": [], "SOUTH": []}
clientes_conectados = []
coches_en_puente = 0  # Nuevo: contador de carros en el puente

def notificar_a_todos():
    """Envía el estado actual a todos los clientes conectados."""
    with bridge_lock:
        estado = {
            "bridge_status": "OCCUPIED" if puente_ocupado else "FREE",
            "current_direction": direccion_actual,
            "waiting_north": len(cola_espera["NORTH"]),
            "waiting_south": len(cola_espera["SOUTH"])
        }
        mensaje = f"STATUS_UPDATE {json.dumps(estado)}\n"
        for cliente_socket in clientes_conectados:
            try:
                cliente_socket.send(mensaje.encode('utf-8'))
            except socket.error:
                # El cliente se desconectó, lo eliminaremos más tarde
                continue

def gestionar_siguiente_carro():
    """Lógica para decidir qué carro cruza a continuación."""
    with bridge_lock:
        global puente_ocupado, direccion_actual, coches_en_puente

        # Si hay carros esperando en la misma dirección y nadie esperando en la dirección opuesta,
        # permitir que sigan cruzando en la misma dirección.
        if direccion_actual and len(cola_espera[direccion_actual]) > 0 and len(cola_espera["NORTH" if direccion_actual == "SOUTH" else "SOUTH"]) == 0:
            cliente_socket, client_address = cola_espera[direccion_actual].pop(0)
            puente_ocupado = True
            coches_en_puente = 1
            print(f"Otorgando permiso al siguiente en cola: {client_address} para ir al {direccion_actual}")
            try:
                cliente_socket.send("GRANT_CROSS\n".encode('utf-8'))
            except (socket.error, BrokenPipeError):
                print(f"El cliente {client_address} se desconectó mientras esperaba. Intentando con el siguiente.")
                coches_en_puente = 0
                gestionar_siguiente_carro()
            return

        # Si no, revisar ambas colas en orden FIFO, sin depender de la dirección previa
        for dir in ["NORTH", "SOUTH"]:
            if len(cola_espera[dir]) > 0:
                cliente_socket, client_address = cola_espera[dir].pop(0)
                puente_ocupado = True
                direccion_actual = dir
                coches_en_puente = 1
                print(f"Otorgando permiso al siguiente en cola: {client_address} para ir al {dir}")
                try:
                    cliente_socket.send("GRANT_CROSS\n".encode('utf-8'))
                except (socket.error, BrokenPipeError):
                    print(f"El cliente {client_address} se desconectó mientras esperaba. Intentando con el siguiente.")
                    coches_en_puente = 0
                    gestionar_siguiente_carro()
                return
        # Si no hay nadie esperando
        puente_ocupado = False
        direccion_actual = None
        coches_en_puente = 0

def handle_client(client_socket, client_address):
    """Maneja la conexión de un solo cliente."""
    global puente_ocupado, direccion_actual, coches_en_puente
    print(f"[NUEVA CONEXIÓN] {client_address} conectado.")
    
    with bridge_lock:
        clientes_conectados.append(client_socket)
    
    # Notificar inmediatamente al nuevo cliente del estado actual
    notificar_a_todos()

    try:
        while True:
            mensaje = client_socket.recv(1024).decode('utf-8').strip()
            if not mensaje:
                break

            partes = mensaje.split()
            comando = partes[0]

            if comando == "REQUEST_CROSS":
                direccion = partes[1]
                with bridge_lock:
                    opuesta = "NORTH" if direccion == "SOUTH" else "SOUTH"
                    if not puente_ocupado or (direccion_actual == direccion and len(cola_espera[opuesta]) == 0):
                        puente_ocupado = True
                        direccion_actual = direccion
                        coches_en_puente += 1
                        print(f"Permiso otorgado a {client_address} para ir al {direccion}. Carros en puente: {coches_en_puente}")
                        try:
                            client_socket.send("GRANT_CROSS\n".encode('utf-8'))
                        except socket.error:
                            coches_en_puente -= 1
                    else:
                        print(f"Carro de {client_address} encolado para ir al {direccion}")
                        cola_espera[direccion].append((client_socket, client_address))
                notificar_a_todos()
            elif comando == "RELEASE_BRIDGE":
                with bridge_lock:
                    coches_en_puente -= 1
                    print(f"Carro de {client_address} liberó el puente. Carros restantes: {coches_en_puente}")
                    if coches_en_puente <= 0:
                        coches_en_puente = 0
                        gestionar_siguiente_carro()
                notificar_a_todos()

    except (ConnectionResetError, BrokenPipeError):
        print(f"[DESCONEXIÓN] {client_address} se desconectó abruptamente.")
    finally:
        with bridge_lock:
            # Eliminar al cliente de la lista de clientes activos
            if client_socket in clientes_conectados:
                clientes_conectados.remove(client_socket)
            # Eliminar al cliente de cualquier cola de espera en la que pudiera estar
            for dir in cola_espera:
                cola_espera[dir] = [(s, a) for s, a in cola_espera[dir] if s != client_socket]
        client_socket.close()
        print(f"[DESCONEXIÓN] {client_address} finalizó la conexión.")
        notificar_a_todos() # Notificar que un cliente se fue

def main():
    HOST = '127.0.0.1'  # localhost
    PORT = 65432
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[ESCUCHANDO] El servidor está escuchando en {HOST}:{PORT}")
    
    # Hilo para notificar a los clientes periódicamente
    threading.Thread(target=lambda: (notificar_a_todos(), time.sleep(2)), daemon=True).start()

    while True:
        client_socket, client_address = server.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    main()