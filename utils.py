import socket
import json
import uuid
import time

HOST = 'localhost'
PORT = 5000
BUFFER_SIZE = 4096
ENCODING = "utf-8"
LINE_SEP = b"\n"

# Buffer de recepción por socket (clave: file descriptor)
_RX_BUFFERS = {}

def new_id() -> str:
    return str(uuid.uuid4())

def now_ts() -> int:
    return int(time.time())

def send_json(sock, obj: dict) -> None:
    #Envía un objeto JSON como UNA línea (JSONL), UTF-8, terminado en '\n'.
    data = (json.dumps(obj, separators=(",", ":"), ensure_ascii=False)).encode(ENCODING) + LINE_SEP
    sock.sendall(data)

def recv_json_lines(sock):
    """
    Generador que entrega 0..N objetos JSON completos por cada llamada,
    manteniendo un buffer por socket. No se traga mensajes pegados ni cortados.
    Uso típico:
        for msg in recv_json_lines(sock):
            handle(msg)
    """
    fd = sock.fileno()
    buf = _RX_BUFFERS.get(fd, b"")
    chunk = sock.recv(4096)
    if not chunk:
        # peer cerró; vaciamos buffer y avisamos al caller
        _RX_BUFFERS.pop(fd, None)
        return None
    buf += chunk
    msgs, start = [], 0
    while True:
        nl = buf.find(LINE_SEP, start)
        if nl < 0:
            break
        line = buf[start:nl].strip()
        if line:
            msgs.append(json.loads(line.decode(ENCODING)))
        start = nl + 1
    _RX_BUFFERS[fd] = buf[start:]  # guarda el resto (posible parcial)
    return msgs
