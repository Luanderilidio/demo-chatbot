$ErrorActionPreference = 'Stop'
$ragRoot = Split-Path -Parent $PSScriptRoot
$ragServerFile = Join-Path $ragRoot 'api\server.cjs'
$ragPort = if ($env:RAG_WEATHER_PORT) { [int]$env:RAG_WEATHER_PORT } else { 3001 }
$ragConnections = @(Get-NetTCPConnection -LocalPort $ragPort -State Listen -ErrorAction SilentlyContinue)
if ($ragConnections.Count -eq 0) { Write-Host 'A API já está encerrada.'; exit 0 }
foreach ($ragConnection in $ragConnections) {
    $ragProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($ragConnection.OwningProcess)"
    if (-not $ragProcess.CommandLine -or $ragProcess.CommandLine.IndexOf($ragServerFile, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "A porta $ragPort pertence a outro processo. Encerre a janela correta manualmente; nenhum processo foi interrompido."
    }
    Stop-Process -Id $ragProcess.ProcessId
}
Write-Host 'API deste projeto encerrada.'
