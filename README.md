# Simulador de Puente de Una Vía

Este proyecto simula la gestión de tráfico en un puente de una sola vía, utilizando una arquitectura distribuida con un servidor central y múltiples clientes (vehículos). Incluye una interfaz gráfica para visualizar el estado del puente, los vehículos y las operaciones de control.

## Componentes principales

- **servidor.py**  
  Gestiona el acceso al puente, controla las colas de espera y comunica el estado a los clientes.

- **interfaz.py**  
  Visualiza la simulación en tiempo real, permite agregar y modificar vehículos, y muestra estadísticas y logs.

- **main.py**  
  Administra el ciclo de vida de los procesos del servidor y la interfaz gráfica.

- **menu.py**  
  Proporciona un menú principal para iniciar y cerrar la simulación.

## Requisitos

- Python 3.8+
- [pygame](https://www.pygame.org/)
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter)
- [Pillow](https://python-pillow.org/) (solo para el menú)
- Carpeta `assets` con imágenes para el menú

Instala las dependencias con:

```bash
pip install pygame customtkinter Pillow
```

o también puede ejecutar:

```bash
pip install -r requirements.txt
```

## Uso

1. Ejecuta `menu.py` para abrir el menú principal.
2. Desde el menú, inicia la simulación. Esto lanzará el servidor y la interfaz gráfica.
3. Usa la interfaz para agregar vehículos, modificar sus parámetros y observar el tráfico en el puente.

## Funcionalidades

- **Agregar vehículo:**  
  Añade un nuevo carro con velocidad, descanso y dirección configurables.

- **Modificar vehículo:**  
  Permite cambiar la velocidad y el tiempo de descanso de cada carro en la simulación.

- **Panel de control:**  
  Muestra el estado del puente, semáforos, colas y un registro de eventos.

## Notas

- Los vehículos no se superponen al panel lateral.
- Solo se pueden modificar los parámetros de velocidad y descanso de los vehículos.
- El menú requiere imágenes en la carpeta `assets` para los iconos.

## Créditos

Franmari Garcia

Magleo Medina

---
