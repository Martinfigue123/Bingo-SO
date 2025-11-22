import sys, json, socket, threading, time
from utils import send_json, recv_json_lines, new_id, now_ts, setup_json_logger, log_event

class BingoClient:
    def __init__(self, host, port, nickname):
        self.host, self.port = host, port
        self.nickname = nickname
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seq_c = 0
        self.player_id = None
        self.game_id = None
        self.matrix = None
        # self.draws keeps tuples (value, draw_n); drawn_numbers is a set de valores para comprobaciones rápidas
        self.draws = []
        self.drawn_numbers = set()
        # Logger por cliente
        safe = "".join(ch for ch in nickname if ch.isalnum() or ch in ("-","_"))
        self.logger = setup_json_logger(f"client-{safe}", f"logs/client_{safe}.ndjson")

    def _send(self, typ, payload):
        self.seq_c += 1
        msg = {
            "type": typ,
            "game_id": self.game_id,
            "player_id": self.player_id,
            "msg_id": new_id(),
            "seq": self.seq_c,
            "ts": now_ts(),
            "payload": payload or {}
        }
        send_json(self.sock, msg)
        log_event(self.logger, ev="tx", type=typ, msg_id=msg["msg_id"], seq=msg["seq"],
                  game_id=self.game_id, player_id=self.player_id, payload=payload)        
        return msg

    def _ack(self, msg_id_ref: str):
        self._send("ACK", {"msg_id_ref": msg_id_ref})

    def run(self):
        self.sock.connect((self.host, self.port))
        threading.Thread(target=self._rx, daemon=True).start()
        # Ejemplo simple: el cliente entra con HELLO y JOIN
        self._send("HELLO", {"proto": "bingo-x/1.0", "nickname": self.nickname})
        time.sleep(0.1)
        self._send("JOIN", {"nickname": self.nickname})
        # loop de consola si lo tienes

    def _rx(self):
        while True:
            msgs = recv_json_lines(self.sock)
            if msgs is None:
                print("[cli] conexión cerrada por el servidor")
                log_event(self.logger, ev="conn_closed")
                return
            msgs = msgs or []
            for m in msgs:
                typ = m.get("type")
                payload = m.get("payload", {})
                mid = m.get("msg_id")
                
                if typ == "WELCOME":
                    self.game_id = m.get("game_id")
                    log_event(self.logger, ev="rx", type="WELCOME", payload=payload)                    
                    
                elif typ == "JOIN_OK":
                    self.player_id = payload.get("player_id")
                    if mid: self._ack(mid)
                    log_event(self.logger, ev="rx", type="JOIN_OK", msg_id=mid, payload=payload)  
                    print(f">> Te uniste al juego {self.game_id} con ID: {self.player_id}")
                    print(f'>> Bienvenido, {self.nickname}!')                  
                    
                elif typ == "START":
                    if mid: self._ack(mid)
                    log_event(self.logger, ev="rx", type="START", msg_id=mid)
                    print(">> La partida ha comenzado!")
                    
                elif typ == "CARD":
                    self.matrix = payload.get("matrix")
                    if mid: self._ack(mid)
                    log_event(self.logger, ev="rx", type="CARD", msg_id=mid, size=len(self.matrix or []))
                    print(">> Recibiste tu cartón:")
                    self.show_card()
                    
                elif typ == "DRAW":
                    val = payload.get("value")
                    log_event(self.logger, ev="rx", type="DRAW", msg_id=mid, value=val,
                              draw_n=payload.get("draw_n"))
                    print(f">> Número sacado: {val}")
                    draw_n = payload.get("draw_n")
                    self.draws.append((val, draw_n))
                    # mantener también un conjunto de valores sacados para comprobaciones de pertenencia
                    if val is not None:
                        self.drawn_numbers.add(val)
                    if mid: self._ack(mid)
                    self.show_card()

                    # --- VERIFICAR VICTORIA ---
                    if self.check_winner():
                        print("\n >> ¡¡¡ BINGO !!! ¡ENVIANDO VICTORIA!")
                        self._send("BINGO", {})
                        log_event(self.logger, ev="bingo_send")
                    
                elif typ == "RESULT":
                    if mid: self._ack(mid)
                    log_event(self.logger, ev="rx", type="RESULT", msg_id=mid, payload=payload)
                    print("Resultado de la partida:")
                    winner = payload.get("winner", {})
                    print(f" >> Ganador: {winner.get('nickname')}\n    (ID: {winner.get('player_id')})")
                    print(f" >> Victoria en {len(self.draws)} números.")
                    
                elif typ == "GAME_OVER":
                    if mid: self._ack(mid)
                    log_event(self.logger, ev="rx", type="GAME_OVER", msg_id=mid)                    
                    print("GAME OVER")
                    return

# Funciones de JUEGO

    def check_winner(self):
        """Revisa si completó línea, columna o diagonal"""
        if not self.matrix: return False
        
        # Filas
        for row in self.matrix:
            if all(num in self.drawn_numbers for num in row):
                return True
        # Columnas
        for col_idx in range(5):
            col = [self.matrix[r][col_idx] for r in range(5)]
            if all(num in self.drawn_numbers for num in col):
                return True
        # Diagonales
        d1 = [self.matrix[i][i] for i in range(5)]
        if all(num in self.drawn_numbers for num in d1):
            return True
        d2 = [self.matrix[i][4-i] for i in range(5)]
        if all(num in self.drawn_numbers for num in d2):
            return True
            
        return False

    def show_card(self):
        print("\n" + "="*30)
        print(" B     I     N     G     O")
        print("="*30)
        for row in self.matrix:
            line = ""
            for num in row:
                if num in self.drawn_numbers:
                    line += " [XX] "
                else:
                    line += f"  {num:02d}  "
            print(line)
        print("="*30 + "\n")

# MAIN

if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print(f"Uso: {sys.argv[0]} HOST PORT NICKNAME [mod]")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    nickname = sys.argv[3]
    is_mod = (len(sys.argv) == 5 and sys.argv[4].lower() == "mod")
    client = BingoClient(host, port, nickname)
    client.sock.connect((host, port))
    threading.Thread(target=client._rx, daemon=True).start()
    # Handshake
    client._send("HELLO", {"proto": "bingo-x/1.0", "nickname": nickname})
    time.sleep(0.1)
    if is_mod:
        # El moderador crea sala y queda auto-inscrito según el server
        client._send("CREATE", {"nickname": nickname})
        print(">> Escribe 'start' para iniciar la partida, 'quit' para salir")
    else:
        client._send("JOIN", {"nickname": nickname})

    # Consola mínima
    try:
        while True:
            cmd = input().strip().lower()
            if cmd == "start" and is_mod:
                client._send("START", {})
            elif cmd == "quit":
                break
    except KeyboardInterrupt:
        pass
        
