[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('backup', 'bootstrap', 'load', 'verify', 'report')]
    [string]$Action,

    [Parameter(Position = 1)]
    [string]$Source,

    [Parameter(Position = 2)]
    [ValidateSet('sample', 'full')]
    [string]$Mode = 'full',

    [string]$Database = 'pharmaflow_source_postgre_v2'
)

$ErrorActionPreference = 'Stop'
$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $packageRoot '..\..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$cli = Join-Path $PSScriptRoot 'source_cli.py'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment not found: $python"
}

$allowedDatabases = @('pharmaflow_source_postgre_v2')
if ($Action -eq 'backup') {
    throw "The previous database was deleted after its verified backup. Use the retained archive under runs\20261104-forecast-schema-v2\backup; no Neon connection was attempted."
}
if ($Database -notin $allowedDatabases) {
    throw "Action '$Action' is restricted to configured database(s): $($allowedDatabases -join ', ')."
}

$arguments = @($cli, $Action)
switch ($Action) {
    'bootstrap' {
        $arguments += @('--database', $Database)
    }
    'load' {
        if (-not $Source) { throw 'Specify a source: longchau, irpd, onyx, or pharma_sales.' }
        $arguments += @($Source, $Mode, '--database', $Database)
    }
    'verify' {
        if (-not $Source) { throw "Specify a source or 'all'." }
        $arguments += @($Source, $Mode, '--database', $Database)
    }
    'report' {
        $arguments += @('--database', $Database)
    }
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
