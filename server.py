import sys, socket, threading, random, time
from utils import send_json, recv_json_lines, new_id, now_ts

class ClientCtx:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.player_id = None
        self.nickname = None
        self.alive = True
        # Fiabilidad de app:
        self.seq_s = 0                    # contador S->C
        self.awaiting_acks = {}           # msg_id -> (msg, ts, retries)

class BingoServer:
    def __init__(self, host, port, max_players=3):
        self.host, self.port = host, port
        self.game_id = new_id()
        self.state = "LOBBY"  # IDLE, LOBBY, RUNNING, FINISHED
        self.lock = threading.Lock()
        self.clients = []
        self.cards = {}
        self.drawn = []
        self.draw_n = 0
        self.max_players = max_players
        # socket del servidor desde el inicio
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen()
        print(f"[srv] listening on {self.host}:{self.port} game_id={self.game_id}")
        print(f"[srv] waiting for up to {self.max_players} players...")
        # Hilo que reintenta mensajes críticos sin ACK
        threading.Thread(target=self._ack_monitor, daemon=True).start()
        while True:
            c, a = self.server.accept()
            ctx = ClientCtx(c, a)
            with self.lock: self.clients.append(ctx)
            threading.Thread(target=self._handle_client, args=(ctx,), daemon=True).start()

    def _handle_client(self, ctx: ClientCtx):
        try:
            while ctx.alive:
                msgs = recv_json_lines(ctx.sock)
                if msgs is None:
                    break
                for msg in msgs or []:
                    self._on_message(ctx, msg)
        except Exception as e:
            print(f"[srv] client {ctx.addr} error: {e}")
        finally:
            ctx.alive = False
            ctx.sock.close()

    # Fiabilidad: envío y ACK 
    def _send(self, ctx: ClientCtx, typ: str, payload: dict, *, critical: bool):
        with self.lock:
            ctx.seq_s += 1
            m = {
                "type": typ,
                "game_id": self.game_id,
                "player_id": ctx.player_id,
                "msg_id": new_id(),
                "seq": ctx.seq_s,
                "ts": now_ts(),
                "payload": payload or {}
            }
            send_json(ctx.sock, m)
            if critical:
                ctx.awaiting_acks[m["msg_id"]] = [m, time.time(), 0]
        return m

    def _broadcast(self, typ: str, payload: dict, *, critical: bool):
        """Envía mensaje a todos los clientes vivos"""
        with self.lock:
            targets = list(self.clients)   # copia estable
        for c in targets:
            if c.alive:
                self._send(c, typ, payload, critical=critical)

    def _ack_monitor(self):
        ACK_TIMEOUT = 2.0
        ACK_RETRIES = 5
        while True:
            time.sleep(0.1)
            now = time.time()
            with self.lock:
                clients = list(self.clients)
            for c in clients:
                if not c.alive:
                    continue
                to_retry = []
                with self.lock:
                    items = list(c.awaiting_acks.items())
                for mid,(m,ts,retries) in items:
                    if now - ts >= ACK_TIMEOUT:
                        if retries >= ACK_RETRIES:
                            print(f"[srv] drop {c.addr}: no ACK for {m['type']}")
                            c.alive = False
                            try: c.sock.shutdown(socket.SHUT_RDWR)
                            except: pass
                            c.sock.close()
                            with self.lock:
                                c.awaiting_acks.pop(mid, None)
                            continue
                        to_retry.append(mid)
                for mid in to_retry:
                    with self.lock:
                        m,_,retries = c.awaiting_acks.get(mid, (None,None,None))
                        if not m: continue
                        send_json(c.sock, m)               # reenvía MISMO msg_id
                        c.awaiting_acks[mid] = [m, now, retries+1]

    def _on_message(self, ctx: ClientCtx, m: dict):
        typ = m.get("type")
        payload = m.get("payload", {})

        if typ == "HELLO":
            # responde WELCOME (no crítico)
            self._send(ctx, "WELCOME",
                       {"max_players": self.max_players, "win_patterns":["ROW","COL","DIAG"]},
                       critical=False)
            print(f"[srv] client -> HELLO! {ctx.addr}")

        elif typ == "CREATE":
            # **Auto-JOIN del moderador** (creador de la sala pasa a ser jugador)
            if self.state != "LOBBY":
                self._send(ctx, "ERROR", {"code":"BAD_STATE","detail":"Ya hay una partida en curso"}, critical=False)
                return
            if not ctx.player_id:
                ctx.player_id = new_id()
                ctx.nickname = payload.get("nickname","moderator")
            # Informar estado de lobby y confirmar ingreso del creador
            self._send(ctx, "JOIN_OK", {
                "player_id": ctx.player_id,
                "players": [{"id": c.player_id, "nick": c.nickname}
                            for c in self.clients if c.player_id]
            }, critical=True)  # requiere ACK
            print(f"[srv] game created by {ctx.nickname} ({ctx.addr}) and joined!")

        elif typ == "JOIN":
            # asigna identidad si viene directo a JOIN (sin CREATE)
            if not ctx.player_id:
                ctx.player_id = new_id()
                ctx.nickname = payload.get("nickname","player")
            self._send(ctx, "JOIN_OK", {
                "player_id": ctx.player_id,
                "players": [{"id": c.player_id, "nick": c.nickname}
                            for c in self.clients if c.player_id]
            }, critical=True)  # requiere ACK
            print(f"[srv] player joined: {ctx.nickname} ({ctx.addr})")
            
            # AUTOSTART: si ya están todos los cupos, arrancar
            with self.lock:
                current = len([c for c in self.clients if c.player_id and c.alive])
            if self.state == "LOBBY" and current >= self.max_players:
                print(f"[srv] max players reached ({current}), starting game...")
                self._start_game()

        elif typ == "ACK":
            mid = payload.get("msg_id_ref")
            if mid:
                ctx.awaiting_acks.pop(mid, None)

        elif typ == "START":
            # Inicio explícito por moderador: START + CARD (+ ACK)
            if self.state != "LOBBY":
                self._send(ctx, "ERROR", {"code":"BAD_STATE","detail":"No en LOBBY"}, critical=False)
                return
            print(f"[srv] game starting by moderator {ctx.nickname} ({ctx.addr})")
            self._start_game()

        elif typ == "BINGO":
            if self.state != "RUNNING":
                return
            # Validación mínima: aceptamos el primero que llegue
            print(f"[srv] BINGO claimed by {ctx.nickname} ({ctx.addr})")
            card = self.cards.get(ctx.player_id)
            if not card or not self.validate_win(card):
                self._send(ctx, "ERROR", {"code":"INVALID_BINGO","detail":"Cartón inválido"}, critical=False)
                return
            self._broadcast("RESULT", {
                "winner": {"player_id": ctx.player_id, "nickname": ctx.nickname},
                "summary": {"draws": self.draw_n}
            }, critical=True)
            self.state = "FINISHED"
            self._broadcast("GAME_OVER", {}, critical=True)

    def _draw_loop(self):
        """Saca números cada 1 segundo"""
        print("[GAME LOOP] Comenzando sorteo...")
        bag = list(range(1,76))
        random.shuffle(bag)
        while self.state == "RUNNING" and bag:
            time.sleep(1.0)
            n = bag.pop()
            self.draw_n += 1
            self.drawn.append((n, self.draw_n))
            # `DRAW` es crítico y exige ACK (para no “dejar atrás” jugadores)
            self._broadcast("DRAW", {"value": n, "draw_n": self.draw_n}, critical=True)
            print(f"[GAME LOOP] Número sorteado: {n} (draw #{self.draw_n})")
            
    def _start_game(self):
        with self.lock:
            if self.state != "LOBBY":
                return
            self.state = "RUNNING"
        # START (ACK)
        print(f"INICIANDO PARTIDA {self.game_id}!")
        self._broadcast("START", {"seed": random.randint(1,10**9)}, critical=True)
        time.sleep(1)
        # Asignar cartas (ACK por cada CARD)
        universe = list(range(1,76))
        for c in list(self.clients):
            if not c.player_id or not c.alive:
                continue
            nums = random.sample(universe, 25)
            matrix = [nums[i*5:(i+1)*5] for i in range(5)]
            self.cards[c.player_id] = matrix
            self._send(c, "CARD", {"matrix": matrix, "size":5, "range":[1,75]}, critical=True)
        # Arrancar loop de DRAW
        threading.Thread(target=self._draw_loop, daemon=True).start()

# Funciones de JUEGO
    
    def validate_win(self, card_matrix):
        """Verifica si el cartón realmente ganó con los números sorteados"""
        # Construir un conjunto con los números ya sorteados (self.drawn guarda tuplas (num, draw_n))
        drawn_numbers = {n for (n, _) in getattr(self, 'drawn', [])}

        # Filas
        for row in card_matrix:
            if all(num in drawn_numbers for num in row):
                return True
        # Columnas
        for col_idx in range(5):
            col = [card_matrix[r][col_idx] for r in range(5)]
            if all(num in drawn_numbers for num in col):
                return True
        # Diagonales
        d1 = [card_matrix[i][i] for i in range(5)]
        if all(num in drawn_numbers for num in d1):
            return True
        d2 = [card_matrix[i][4-i] for i in range(5)]
        if all(num in drawn_numbers for num in d2):
            return True

        return False


# MAIN

if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("Uso: python server.py [max_players]")
        print(" max_players: número máximo de jugadores.")
        print(" Si se omite, por defectos son 3 jugadores máximo.")
        sys.exit(1)
    if len(sys.argv) == 2:
        srv = BingoServer('localhost', 5000, max_players=int(sys.argv[1]))
    else:
        srv = BingoServer('localhost', 5000)
    srv.start()