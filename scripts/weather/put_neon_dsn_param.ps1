<#
.SYNOPSIS
  Store WEATHER_NEON_DSN from .env as an SSM SecureString for the weather planner Lambda.

.DESCRIPTION
  The value never appears on the console or in the command line: it is read from .env into memory,
  written to a short-lived temp file passed via file://, and the file is deleted immediately.
  Terraform does not manage this parameter, so the secret never enters Terraform state.
#>
[CmdletBinding()]
param(
  [string]$Profile = "my-aws",
  [string]$Region = "ap-southeast-1",
  [string]$Name = "/pharmaflow/dev/weather/neon_dsn",
  [string]$RepoRoot = ""
)
$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
$env:AWS_PROFILE = $Profile

$envFile = Join-Path $RepoRoot ".env"
$line = Get-Content $envFile | Where-Object { $_ -match '^\s*WEATHER_NEON_DSN\s*=' } | Select-Object -First 1
if (-not $line) { throw "WEATHER_NEON_DSN is not set in .env" }
$value = ($line -replace '^\s*WEATHER_NEON_DSN\s*=\s*', '').Trim().Trim('"').Trim("'")
if ($value -notmatch '^postgres(ql)?://') { throw "WEATHER_NEON_DSN does not look like a PostgreSQL URL" }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("neon-dsn-" + [guid]::NewGuid().ToString("N") + ".txt")
try {
  [IO.File]::WriteAllText($tmp, $value, (New-Object Text.UTF8Encoding($false)))
  $null = aws ssm put-parameter --name $Name --type SecureString --key-id alias/aws/ssm --overwrite `
    --value "file://$tmp" --region $Region --output json
  if ($LASTEXITCODE -ne 0) { throw "put-parameter failed" }
} finally {
  if (Test-Path $tmp) { Remove-Item -Force $tmp }
  Remove-Variable value, line -ErrorAction SilentlyContinue
}
$meta = aws ssm describe-parameters --region $Region --parameter-filters "Key=Name,Values=$Name" --output json | ConvertFrom-Json
$p = $meta.Parameters[0]
[pscustomobject]@{ name = $p.Name; type = $p.Type; key = $p.KeyId; version = $p.Version; last_modified = $p.LastModifiedDate } | Format-List
