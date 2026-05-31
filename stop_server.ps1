$connections = netstat -ano | Select-String ':8000'

if (-not $connections) {
    Write-Host 'Local server on port 8000 is not running.'
    exit 0
}

$processIds = $connections |
    ForEach-Object { ($_ -split '\s+')[-1] } |
    Where-Object { $_ -match '^\d+$' -and $_ -ne '0' } |
    Sort-Object -Unique

foreach ($processId in $processIds) {
    Stop-Process -Id ([int]$processId) -ErrorAction SilentlyContinue
    Write-Host "Stopped process $processId"
}
