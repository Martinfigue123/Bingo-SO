import socket
import threading
import time
import uuid
from utils import HOST, PORT, send_json, receive_json

class BingoClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        self.running = True

    def receive_messages(self):
        """Hilo para escuchar mensajes del servidor continuamente"""
        while self.running:
            msg = receive_json(self.sock)
            if msg:
                print(f"\n[SERVIDOR DICE]: {msg}")
                # Aquí podrías manejar diferentes tipos de mensajes
                if msg.get("type") == "WELCOME":
                    print(">>> ¡Sala Creada/Conectada exitosamente!")
            else:
                print("\n[DESCONECTADO] El servidor cerró la conexión.")
                self.running = False
                break

    def start(self):
        # Iniciar hilo de escucha
        recv_thread = threading.Thread(target=self.receive_messages)
        recv_thread.daemon = True
        recv_thread.start()

        print(f"Conectado a {HOST}:{PORT}")
        print("Escribe un comando (CREATE, JOIN, EXIT):")

        # Bucle principal para enviar comandos (Simulación manual)
        while self.running:
            action = input("")
            
            payload = {}
            msg_type = ""

            if action.upper() == "CREATE":
                msg_type = "CREATE"
                payload = {"password": "123", "max_players": 3, "version": "1.0"}
            
            elif action.upper() == "JOIN":
                msg_type = "JOIN"
                payload = {"game_id": "???", "nickname": "Jugador1"}
            
            elif action.upper() == "EXIT":
                self.running = False
                break
            else:
                print("Comando no reconocido en esta demo.")
                continue

            message = {
                "type": msg_type,
                "game_id": None, # Se llenaría con el real
                "player_id": None,
                "msg_id": str(uuid.uuid4()),
                "seq": 1,
                "ts": int(time.time()),
                "payload": payload
            }
            
            send_json(self.sock, message)
        
        self.sock.close()

if __name__ == "__main__":
    client = BingoClient()
    client.start()