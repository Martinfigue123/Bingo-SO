import socket
import threading
import uuid
import time
import random
from utils import HOST, PORT, send_json, receive_json

class BingoServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen()
        
        self.clients_data = {} 
        self.clients_sockets = [] # Lista solo de sockets para el broadcast
        
        self.lock = threading.Lock()
        self.game_state = "IDLE" 
        self.game_id = None
        self.drawn_numbers = [] # Números que ya salieron

    def generate_card(self):
        """Genera una matriz de Bingo 5x5 clásica (1-75)"""
        card = []
        # Columnas B I N G O 
        ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
        
        # Generamos 5 columnas verticales
        cols = []
        for r_min, r_max in ranges:
            # Sample elige 5 números únicos del rang
            col = random.sample(range(r_min, r_max + 1), 5)
            cols.append(col)
        
        for i in range(5):
            row = [cols[j][i] for j in range(5)]
            card.append(row)
            
        
        card[2][2] = 0 # Centro del carton, generalmente es espacio libre
        return card

    def broadcast(self, message):
        """Envía un mensaje a todos los clientes conectados."""
        print(f"[BROADCAST] Enviando: {message['type']}")
        for sock in self.clients_sockets:
            try:
                send_json(sock, message)
            except:
                pass

    def start_game_logic(self):
        """Inicia la secuencia de juego (START -> CARDS -> DRAWS)"""
        print("--- INICIANDO PARTIDA ---")
        self.game_state = "RUNNING"
        
        #Enviar START
        self.broadcast({"type": "START", "payload": {"seed": 123}})
        time.sleep(1)
        
        #Generar y enviar Cartones (CARD) a cada jugador
        for sock in self.clients_sockets:
            card_matrix = self.generate_card()
            # Guardamos el cartón en los datos del cliente para validarlo después
            if sock in self.clients_data:
                self.clients_data[sock]['card'] = card_matrix
            
            msg_card = {
                "type": "CARD",
                "game_id": self.game_id,
                "payload": {
                    "matrix": card_matrix,
                    "size": 5,
                    "range": [1, 75]
                }
            }
            send_json(sock, msg_card)
        
        # Iniciar hilo que anuncia números
        threading.Thread(target=self.game_loop, daemon=True).start()

    def game_loop(self):
        """Bucle principal que saca números cada 3 segundos"""
        print("[GAME LOOP] Comenzando sorteo...")
        available_numbers = list(range(1, 76))
        random.shuffle(available_numbers)
        
        draw_count = 0
        
        while self.game_state == "RUNNING" and available_numbers:
            time.sleep(6) # Esperar 6 segundos entre números
            
            number = available_numbers.pop(0)
            self.drawn_numbers.append(number)
            draw_count += 1
            
            msg_draw = {
                "type": "DRAW",
                "game_id": self.game_id,
                "payload": {
                    "value": number,
                    "draw_n": draw_count
                }
            }
            self.broadcast(msg_draw)
            print(f"--> Sorteado: {number}")

    def handle_client(self, client_socket, client_address):
        print(f'[NUEVA CONEXIÓN] {client_address}')
        with self.lock:
            self.clients_sockets.append(client_socket)
            # Inicializamos data vacía
            self.clients_data[client_socket] = {"id": None, "nick": "Anon", "card": []}
            
        try:
            connected = True
            while connected:
                msg = receive_json(client_socket)
                if msg:
                    cmd = msg.get('type')
                    
                    if cmd == 'CREATE':
                        if self.game_state == 'IDLE':
                            self.game_state = 'LOBBY'
                            self.game_id = str(uuid.uuid4())
                            # Iniciamos la partida automáticamente tras 10 segundos
                            # O podrías esperar un comando 'START' explícito del cliente moderador
                            threading.Timer(15.0, self.start_game_logic).start()
                            print("[SERVER] La partida iniciará en 15 segundos...")
                            
                            response = {'type': 'WELCOME', 'game_id': self.game_id}
                            send_json(client_socket, response)
                        else:
                            send_json(client_socket, {'type': 'ERROR', 'payload': 'Ya existe partida'})

                    elif cmd == 'JOIN':
                        player_id = str(uuid.uuid4())
                        nick = msg['payload'].get('nickname', 'Player')
                        
                        # Actualizar info del cliente
                        self.clients_data[client_socket]['id'] = player_id
                        self.clients_data[client_socket]['nick'] = nick
                        
                        response = {
                            'type': 'JOIN_OK',
                            'game_id': self.game_id,
                            'player_id': player_id,
                            'slot': len(self.clients_sockets)
                        }
                        send_json(client_socket, response)

                    elif cmd == 'EXIT':
                        connected = False
                else:
                    connected = False
        except Exception as e:
            print(f"Error con cliente: {e}")
        finally:
            with self.lock:
                if client_socket in self.clients_sockets:
                    self.clients_sockets.remove(client_socket)
                if client_socket in self.clients_data:
                    del self.clients_data[client_socket]
            client_socket.close()

    def start(self):
        print(f'[INICIANDO] Servidor en {HOST}:{PORT}')
        while True:
            client_sock, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_sock, addr)).start()

if __name__ == '__main__':
    server = BingoServer()
    server.start()