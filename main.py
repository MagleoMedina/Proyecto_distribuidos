import subprocess
import time
import sys

class SimulacionManager:
    def __init__(self):
        self.procesos = []

    def iniciar_procesos(self):
        """Inicia los procesos del servidor y del visualizador de la simulación."""
        print("Iniciando el servidor...")
        servidor_proceso = subprocess.Popen([sys.executable, "servidor.py"])
        self.procesos.append(servidor_proceso)
        time.sleep(2)  # Darle tiempo al servidor para que inicie

        print("Iniciando el Visualizador de la simulación...")
        visualizador_proceso = subprocess.Popen([sys.executable, "interfaz.py"])
        self.procesos.append(visualizador_proceso)
        print("\nSimulación en marcha. Cierra esta ventana para terminar todos los procesos.")

    def terminar_procesos(self):
        """Termina todos los procesos de la simulación."""
        print("\nTerminando la simulación...")
        for p in self.procesos:
            p.terminate()
        print("Todos los procesos han sido terminados.")

    def close_window(self):
        """Cierra todos los procesos de la simulación (incluye la ventana de interfaz)."""
        self.terminar_procesos()

    def run(self):
        """Inicia la simulación y monitorea los procesos."""
        self.iniciar_procesos()
        try:
            while True:
                for i, p in enumerate(self.procesos):
                    ret = p.poll()
                    if ret is not None:
                        print(f"[AVISO] El proceso {i} (PID {p.pid}) terminó con código {ret}.")
                time.sleep(1)
        except KeyboardInterrupt:
            self.terminar_procesos()

