import socket
import threading
import uuid
from utils import HOST, PORT, send_json, receive_json

class BingoServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen()
        self.clients = [] # Lista de clientes conectados
        self.lock = threading.Lock() # Lock para manejar acceso concurrente
        self.game_state = "IDLE" # Estado del juego: IDLE, RUNNING, FINISHED
        self.game_id = None # ID del juego actual

    def broadcast(self, message):
        """Envía un mensaje a todos los clientes conectados."""
        print(f"[BROADCAST] Enviando: {message['type']}")
        for client in self.clients:
            send_json(client, message)

    def handle_client(self, client_socket, client_address):
        '''Maneja la comunicación con un cliente conectado.'''
        print(f'[NUEVA CONEXIÓN] {client_address} conectado.')
        self.clients.append(client_socket)
        try:

            connected = True
            while connected:
                msg = receive_json(client_socket)
                if msg:
                    print(f'[{client_address}] Mensaje recivido: {msg}')

                    # Maquina de estados
                    cmd = msg.get('type')
                    if cmd == 'CREATE':
                        self.game_state = 'LOBBY'
                        self.game_id = str(uuid.uuid4())
                        response = {
                            'type': 'WELCOME',
                            'game_id': self.game_id,
                            'max_players': msg['payload']['max_players'],
                            'players': []
                        }
                        send_json(client_socket, response)

                    elif cmd == 'JOIN':
                        # Logica de respuesta para unirse a un juego
                        response = {
                            'type': 'JOIN_OK',
                            'game_id': self.game_id,
                            'players_id': str(uuid.uuid4()),
                            'players': [],
                            'slot': len(self.clients)
                        }
                        send_json(client_socket, response)

                    elif cmd == 'EXIT':
                        connected = False
                        print(f'[DESCONEXIÓN] {client_address} se ha desconectado.')
                
                else:
                    connected = False
        except Exception as e:
            print(f'[ERROR] Error en la comunicación con {client_address}: {e}')
        finally:
            print(f'[CERRANDO] Cerrando conexión con {client_address}')
            client_socket.close()
            if client_socket in self.clients:
                self.clients.remove(client_socket)

    def start(self):
        print(f'[INICIANDO] Servidor iniciando en {HOST}:{PORT}')
        while True:
            client_socket, client_adress = self.server_socket.accept()
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_adress))
            client_thread.start()
            print(f'[CONEXIONES ACTIVAS] {threading.active_count() - 1}')
    
if __name__ == '__main__':
    server = BingoServer()
    server.start()