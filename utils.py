import socket
import json

HOST = 'localhost'
PORT = 5000
BUFFER_SIZE = 4096

def send_json(sock, data_dict):
    # Envía un diccionario como JSON a través del socket
    try:
        json_str = json.dumps(data_dict)
        msg = f"{json_str}\n"
        sock.sendall(msg.encode('utf-8'))
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def receive_json(sock):
    """
    Recibe datos del socket hasta encontrar un salto de línea (\n).
    """
    try:
        data = sock.recv(BUFFER_SIZE)
        if not data:
            return None
        
        decoded_data = data.decode('utf-8').strip()
        # Si llegan varios mensajes pegados, tomamos el primero
        messages = decoded_data.split('\n')
        
        if not messages[0]:
            return None
            
        return json.loads(messages[0])
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"Error recibiendo mensaje: {e}")
        return None