import socket
import json
import struct

# Configuracion Global
HOST = 'localhost' # Localhost para pruebas
PORT = 5000
BUFFER_SIZE = 4096

def send_json(sock, data):
    """Envía un objeto JSON a través del socket."""
    try:
        json_str = json.dumps(data)
        msg =f"{json_str}\n"
        sock.sendall(msg.encode('utf-8'))
    except Exception as e:
        print(f"Error al enviar el mensaje: {e}")

def receive_json(sock):
    """Recibe un objeto JSON a través del socket."""
    try:
        data = sock.recv(BUFFER_SIZE)
        if not data:
            return None
        
        decoded_data = data.decode('utf-8').strip()
        messages = decoded_data.split('\n')
        if not messages[0]:
            return None
        
        return json.loads(messages[0])
    except json.JSONDecodeError as e:
        print(f"Error al decodificar JSON: {e}")
        return None
    except Exception as e:
        print(f"Error al recibir el mensaje: {e}")
        return None
    