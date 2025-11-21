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
        self.my_card = [] # Aquí guardaremos el cartón

    def print_card(self):
        """Imprime la matriz del cartón de forma bonita"""
        print("\n--- MI CARTÓN ---")
        print(" B   I   N   G   O")
        for row in self.my_card:
            # Formato para alinear números: {:2} ocupa 2 espacios
            print(" ".join("{:2}".format(num) for num in row))
        print("-----------------\n")

    def receive_messages(self):
        while self.running:
            msg = receive_json(self.sock)
            if msg:
                tipo = msg.get("type")
                
                if tipo == "WELCOME":
                    print(f">>> [SISTEMA] Sala creada ID: {msg.get('game_id')}")
                elif tipo == "JOIN_OK":
                    print(f">>> [SISTEMA] Unido exitosamente.")
                
                elif tipo == "START":
                    print("\n>>> [JUEGO] ¡LA PARTIDA HA COMENZADO!")
                
                elif tipo == "CARD":
                    # Guardamos y mostramos el cartón
                    self.my_card = msg["payload"]["matrix"]
                    print(f">>> [JUEGO] ¡Recibiste tu cartón!")
                    self.print_card()
                    
                elif tipo == "DRAW":
                    # Mostrar el número sorteado
                    num = msg["payload"]["value"]
                    n_draw = msg["payload"]["draw_n"]
                    print(f"\n>>> [SORTEO #{n_draw}] ¡Salió el número {num}!")
                    
                elif tipo == "ERROR":
                    print(f">>> [ERROR] {msg.get('payload')}")
            else:
                print("\n[DESCONECTADO]")
                self.running = False
                break

    def start(self):
        threading.Thread(target=self.receive_messages, daemon=True).start()
        print(f"Conectado a {HOST}:{PORT}")
        print("Comandos: CREATE, JOIN nickname, EXIT")

        while self.running:
            inp = input()
            parts = inp.split(" ")
            action = parts[0].upper()
            
            msg_type = ""
            payload = {}

            if action == "CREATE":
                msg_type = "CREATE"
                payload = {"max_players": 3}
            
            elif action == "JOIN":
                # Permite escribir: JOIN Nombre
                nick = parts[1] if len(parts) > 1 else "Jugador"
                msg_type = "JOIN"
                payload = {"nickname": nick}
            
            elif action == "EXIT":
                self.running = False
                break
            else:
                continue # Ignorar otros inputs

            message = {
                "type": msg_type,
                "game_id": None,
                "msg_id": str(uuid.uuid4()),
                "payload": payload
            }
            send_json(self.sock, message)
        
        self.sock.close()

if __name__ == "__main__":
    client = BingoClient()
    client.start()