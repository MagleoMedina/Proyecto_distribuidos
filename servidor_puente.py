import socket
import threading
import json
import time

# --- Estado Compartido del Puente ---
# Esta sección debe ser segura para hilos (thread-safe)
bridge_lock = threading.RLock()
puente_ocupado = False
direccion_actual = None
cola_espera = {"NORTH": [], "SOUTH": []}
clientes_conectados = []
coches_en_puente = 0  # Nuevo: contador de carros en el puente

# --- NUEVO: IDs de carros cruzando el puente ---
carros_cruzando = []

def notificar_a_todos():
    """Envía el estado actual a todos los clientes conectados."""
    with bridge_lock:
        estado = {
            "bridge_status": "OCCUPIED" if puente_ocupado else "FREE",
            "current_direction": direccion_actual,
            "waiting_north": len(cola_espera["NORTH"]),
            "waiting_south": len(cola_espera["SOUTH"]),
            "crossing_cars": carros_cruzando[:]  # Copia de la lista
        }
        mensaje = f"STATUS_UPDATE {json.dumps(estado)}\n"
        for cliente_socket in clientes_conectados:
            try:
                cliente_socket.send(mensaje.encode('utf-8'))
            except socket.error:
                # El cliente se desconectó, lo eliminaremos más tarde
                continue

def gestionar_siguiente_carro():
    """Lógica justa para decidir qué carro cruza a continuación, alternando direcciones."""
    global puente_ocupado, direccion_actual, coches_en_puente, carros_cruzando

    # Determinar el orden de chequeo para ser justos.
    # Priorizamos la dirección opuesta a la que acaba de cruzar.
    if direccion_actual == "NORTH":
        direcciones_a_chequear = ["SOUTH", "NORTH"]
    elif direccion_actual == "SOUTH":
        direcciones_a_chequear = ["NORTH", "SOUTH"]
    else:
        # Si no había dirección (puente libre), usamos un orden por defecto.
        direcciones_a_chequear = ["NORTH", "SOUTH"]

    # Revisar las colas en el orden de prioridad que acabamos de determinar.
    for dir in direcciones_a_chequear:
        if len(cola_espera[dir]) > 0:
            cliente_socket, client_address, car_id = cola_espera[dir].pop(0)
            puente_ocupado = True
            direccion_actual = dir
            coches_en_puente = 1
            carros_cruzando = [car_id]
            print(f"Alternando dirección. Otorgando permiso a {client_address} (Carro {car_id}) para ir al {dir}")
            try:
                cliente_socket.send("GRANT_CROSS\n".encode('utf-8'))
            except (socket.error, BrokenPipeError):
                print(f"El cliente {client_address} se desconectó mientras esperaba. Intentando con el siguiente.")
                coches_en_puente = 0
                carros_cruzando = []
                gestionar_siguiente_carro()
            return
    puente_ocupado = False
    direccion_actual = None
    coches_en_puente = 0
    carros_cruzando = []

def handle_client(client_socket, client_address):
    """Maneja la conexión de un solo cliente."""
    global puente_ocupado, direccion_actual, coches_en_puente, carros_cruzando
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
                # Espera: REQUEST_CROSS <DIRECCION> <CAR_ID>
                direccion = partes[1]
                car_id = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else str(client_address)
                with bridge_lock:
                    opuesta = "NORTH" if direccion == "SOUTH" else "SOUTH"
                    if not puente_ocupado or (direccion_actual == direccion and len(cola_espera[opuesta]) == 0):
                        puente_ocupado = True
                        direccion_actual = direccion
                        coches_en_puente += 1
                        if car_id not in carros_cruzando:
                            carros_cruzando.append(car_id)
                        print(f"Permiso otorgado a {client_address} (Carro {car_id}) para ir al {direccion}. Carros en puente: {coches_en_puente}")
                        try:
                            client_socket.send("GRANT_CROSS\n".encode('utf-8'))
                        except socket.error:
                            coches_en_puente -= 1
                            if car_id in carros_cruzando:
                                carros_cruzando.remove(car_id)
                    else:
                        print(f"Carro de {client_address} (Carro {car_id}) encolado para ir al {direccion}")
                        cola_espera[direccion].append((client_socket, client_address, car_id))
                notificar_a_todos()
            elif comando == "RELEASE_BRIDGE":
                # No se requiere car_id aquí, pero lo buscamos por si acaso
                car_id = None
                # Buscar el id en la lista de cruzando por el socket
                with bridge_lock:
                    # Buscar el id del carro en carros_cruzando (por socket)
                    for cid in list(carros_cruzando):
                        if isinstance(cid, int) or (isinstance(cid, str) and cid.isdigit()):
                            car_id = cid
                            break
                    coches_en_puente -= 1
                    if car_id and car_id in carros_cruzando:
                        carros_cruzando.remove(car_id)
                    print(f"Carro de {client_address} (Carro {car_id}) liberó el puente. Carros restantes: {coches_en_puente}")
                    if coches_en_puente <= 0:
                        coches_en_puente = 0
                        gestionar_siguiente_carro()
                notificar_a_todos()
    except (ConnectionResetError, BrokenPipeError):
        print(f"[DESCONEXIÓN] {client_address} se desconectó abruptamente.")
    finally:
        with bridge_lock:
            if client_socket in clientes_conectados:
                clientes_conectados.remove(client_socket)
            for dir in cola_espera:
                cola_espera[dir] = [(s, a, cid) for s, a, cid in cola_espera[dir] if s != client_socket]
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