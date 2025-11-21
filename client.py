import socket
import threading
import time
import uuid
from utils import HOST, PORT, send_json, receive_json

class BingoClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((HOST, PORT))
        except:
            print("Error conectando al servidor.")
            exit()
            
        self.running = True
        self.my_card = []
        self.marked_numbers = []

    def check_winner(self):
        """Revisa si completó línea, columna o diagonal"""
        if not self.my_card: return False
        
        # Filas
        for row in self.my_card:
            if all(num in self.marked_numbers for num in row): return True
        # Columnas
        for col_idx in range(5):
            col = [self.my_card[r][col_idx] for r in range(5)]
            if all(num in self.marked_numbers for num in col): return True
        # Diagonales
        d1 = [self.my_card[i][i] for i in range(5)]
        if all(num in self.marked_numbers for num in d1): return True
        d2 = [self.my_card[i][4-i] for i in range(5)]
        if all(num in self.marked_numbers for num in d2): return True
            
        return False

    def show_card(self):
        print("\n" + "="*30)
        print(" B     I     N     G     O")
        print("="*30)
        for row in self.my_card:
            line = ""
            for num in row:
                if num in self.marked_numbers:
                    line += " [XX] "
                else:
                    line += f"  {num:02d}  "
            print(line)
        print("="*30 + "\n")

    def receive_messages(self):
        while self.running:
            msg = receive_json(self.sock)
            if msg:
                tipo = msg.get("type")
                payload = msg.get("payload", {})

                if tipo == "WELCOME":
                    print(f">>> [SISTEMA] Sala creada. Esperando jugadores...")
                elif tipo == "JOIN_OK":
                    print(f">>> [SISTEMA] Unido exitosamente.")
                elif tipo == "START":
                    print(f"\n>>> [JUEGO] ¡COMENZÓ LA PARTIDA!")
                elif tipo == "CARD":
                    self.my_card = payload["matrix"]
                    self.marked_numbers = []
                    print("\n>>> [JUEGO] ¡Cartón recibido!")
                    self.show_card()
                
                elif tipo == "DRAW":
                    num = payload["value"]
                    print(f"\n>>> [SORTEO] Salió el {num}")
                    self.marked_numbers.append(num)
                    self.show_card()
                    
                    # --- VERIFICAR VICTORIA ---
                    if self.check_winner():
                        print("\n!!! BINGO !!! ¡ENVIANDO VICTORIA!")
                        bingo_msg = {
                            "type": "BINGO",
                            "msg_id": str(uuid.uuid4()),
                            "payload": {"card": self.my_card}
                        }
                        send_json(self.sock, bingo_msg)

                elif tipo == "RESULT":
                    print(f"\n>>> [FIN] ¡GANÓ {payload.get('winner')}!")
                elif tipo == "GAME_OVER":
                    print(">>> [SISTEMA] Juego terminado.")
                    self.running = False
            else:
                self.running = False
                break

    def start(self):
        threading.Thread(target=self.receive_messages, daemon=True).start()
        print(f"Conectado a {HOST}:{PORT}")
        print("Comandos: CREATE, JOIN <nombre>, EXIT")

        while self.running:
            try:
                inp = input()
                if not inp: continue
                parts = inp.split()
                cmd = parts[0].upper()
                
                msg_type = ""
                payload = {}
                
                if cmd == "CREATE":
                    msg_type = "CREATE"
                    payload = {"max_players": 3}
                elif cmd == "JOIN":
                    nick = parts[1] if len(parts) > 1 else "Jugador"
                    msg_type = "JOIN"
                    payload = {"nickname": nick}
                elif cmd == "EXIT":
                    self.running = False
                    break
                else:
                    continue
                
                send_json(self.sock, {
                    "type": msg_type,
                    "msg_id": str(uuid.uuid4()),
                    "payload": payload
                })
            except:
                break
        self.sock.close()

if __name__ == "__main__":
    client = BingoClient()
    client.start()