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
        self.clients_sockets = [] 
        
        self.lock = threading.Lock()
        self.game_state = "IDLE" 
        self.game_id = None
        self.drawn_numbers = [] # Historial de números sorteados

    def generate_card(self):
        """Genera matriz 5x5 con rangos B-I-N-G-O"""
        card = []
        ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
        cols = [random.sample(range(r[0], r[1] + 1), 5) for r in ranges]
        
        # Transponer columnas a filas
        for i in range(5):
            row = [cols[j][i] for j in range(5)]
            card.append(row)
        return card

    def validate_win(self, card_matrix):
        """Verifica si el cartón realmente ganó con los números sorteados"""
        # Filas
        for row in card_matrix:
            if all(num in self.drawn_numbers for num in row): return True
        # Columnas
        for col_idx in range(5):
            col = [card_matrix[r][col_idx] for r in range(5)]
            if all(num in self.drawn_numbers for num in col): return True
        # Diagonales
        d1 = [card_matrix[i][i] for i in range(5)]
        if all(num in self.drawn_numbers for num in d1): return True
        d2 = [card_matrix[i][4-i] for i in range(5)]
        if all(num in self.drawn_numbers for num in d2): return True
            
        return False

    def broadcast(self, message):
        """Envía mensaje a todos"""
        print(f"[BROADCAST] Enviando: {message['type']}")
        for sock in self.clients_sockets:
            try:
                send_json(sock, message)
            except:
                pass

    def start_game_logic(self):
        """Inicia la partida y el sorteo"""
        print("--- INICIANDO PARTIDA ---")
        self.game_state = "RUNNING"
        self.drawn_numbers = []
        
        self.broadcast({"type": "START", "payload": {"seed": 123}})
        time.sleep(1)
        
        # Enviar cartones
        for sock in self.clients_sockets:
            card_matrix = self.generate_card()
            if sock in self.clients_data:
                self.clients_data[sock]['card'] = card_matrix
            
            msg_card = {
                "type": "CARD",
                "game_id": self.game_id,
                "payload": {"matrix": card_matrix}
            }
            send_json(sock, msg_card)
        
        # Hilo del sorteo
        threading.Thread(target=self.game_loop, daemon=True).start()

    def game_loop(self):
        """Saca números cada 1 segundo"""
        print("[GAME LOOP] Comenzando sorteo...")
        available = list(range(1, 76))
        random.shuffle(available)
        draw_count = 0
        
        # Sorteamos números mientras estemos RUNNING (nadie haya ganado)
        while self.game_state == "RUNNING" and available:
            time.sleep(4) # Velocidad del sorteo 
            
            number = available.pop(0)
            self.drawn_numbers.append(number)
            draw_count += 1
            
            msg = {
                "type": "DRAW", 
                "payload": {"value": number, "draw_n": draw_count}
            }
            self.broadcast(msg)
            print(f"--> Sorteado: {number}")

    def handle_client(self, client_socket, client_address):
        print(f'[CONEXIÓN] {client_address}')
        with self.lock:
            self.clients_sockets.append(client_socket)
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
                            # Inicia automáticamente en 10 segundos
                            threading.Timer(10.0, self.start_game_logic).start()
                            print("[SERVER] Partida inicia en 10s...")
                            send_json(client_socket, {'type': 'WELCOME', 'game_id': self.game_id})
                        else:
                            send_json(client_socket, {'type': 'ERROR', 'payload': 'Ya existe partida'})

                    elif cmd == 'JOIN':
                        pid = str(uuid.uuid4())
                        nick = msg['payload'].get('nickname', 'Player')
                        self.clients_data[client_socket]['id'] = pid
                        self.clients_data[client_socket]['nick'] = nick
                        
                        send_json(client_socket, {
                            'type': 'JOIN_OK', 'player_id': pid, 'slot': len(self.clients_sockets)
                        })

                    elif cmd == 'BINGO':
                        # ALGUIEN GANA
                        nick = self.clients_data[client_socket]['nick']
                        card = self.clients_data[client_socket]['card']
                        
                        if self.validate_win(card):
                            print(f"¡GANADOR: {nick}!")
                            self.game_state = "FINISHED" # Detener sorteo
                            
                            # Anunciar ganador
                            self.broadcast({
                                "type": "RESULT",
                                "payload": {"winner": nick}
                            })
                            
                            # Terminar juego
                            time.sleep(1)
                            self.broadcast({"type": "GAME_OVER", "payload": {}})
                            
                            # Resetear servidor
                            self.game_state = "IDLE"
                            self.drawn_numbers = []
                            self.clients_data = {}
                            self.clients_sockets = []
                            connected = False
                        else:
                            print(f"Falso Bingo de {nick}")

                    elif cmd == 'EXIT':
                        connected = False
                else:
                    connected = False
        except Exception as e:
            print(f"Error cliente: {e}")
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
            client, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client, addr)).start()

if __name__ == '__main__':
    server = BingoServer()
    server.start()