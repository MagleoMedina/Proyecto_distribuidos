import subprocess
import time
import sys
import pygame

def main():
    procesos = []

    # Iniciar el servidor en un proceso separado
    print("Iniciando el servidor...")
    servidor_proceso = subprocess.Popen([sys.executable, "servidor_puente.py"])
    procesos.append(servidor_proceso)
    time.sleep(2)  # Darle tiempo al servidor para que inicie

    # Iniciar el Dashboard de Estadísticas
    print("Iniciando el Dashboard de Estadísticas...")
    dashboard_proceso = subprocess.Popen([sys.executable, "dashboard_estadisticas.py"])
    procesos.append(dashboard_proceso)
    time.sleep(1)

    # Iniciar el Visualizador centralizado
    print("Iniciando el Visualizador de la simulación...")
    visualizador_proceso = subprocess.Popen([sys.executable, "interfaz.py"])
    procesos.append(visualizador_proceso)
    
    print("\nSimulación en marcha. Cierra esta ventana para terminar todos los procesos.")

    try:
        # Monitorear si algún proceso termina inesperadamente
        while True:
            for i, p in enumerate(procesos):
                ret = p.poll()
                if ret is not None:
                    print(f"[AVISO] El proceso {i} (PID {p.pid}) terminó con código {ret}.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTerminando la simulación...")
        for p in procesos:
            # Usar terminate() para asegurar que los procesos hijos se cierren
            p.terminate()
        print("Todos los procesos han sido terminados.")

if __name__ == "__main__":
    main()

    