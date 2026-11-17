<#
.SYNOPSIS
  Push .runtime/weather/weather_lambda.zip to the three weather Lambda functions (code only).

.DESCRIPTION
  Infra (memory, timeout, env vars, IAM, triggers) is owned by Terraform; this script only calls
  update-function-code and waits for each function to finish updating. Region is fixed to ap-southeast-1.
#>
[CmdletBinding()]
param(
  [string]$Profile = "my-aws",
  [string]$Region = "ap-southeast-1",
  [string[]]$Functions = @("pharmaflow-dev-weather-planner", "pharmaflow-dev-weather-worker", "pharmaflow-dev-weather-reconciler"),
  [string]$RepoRoot = ""
)
$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
$env:AWS_PROFILE = $Profile
$zip = Join-Path $RepoRoot ".runtime\weather\weather_lambda.zip"
if (-not (Test-Path $zip)) { throw "Missing $zip; run scripts/weather/build_lambda.ps1 first" }
$localB64 = & (Join-Path $RepoRoot ".venv\Scripts\python.exe") -B -c "import base64,hashlib,sys;print(base64.b64encode(hashlib.sha256(open(sys.argv[1],'rb').read()).digest()).decode())" $zip

$results = foreach ($fn in $Functions) {
  $resp = aws lambda update-function-code --function-name $fn --zip-file "fileb://$zip" --region $Region --output json | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) { throw "update-function-code failed for $fn" }
  aws lambda wait function-updated-v2 --function-name $fn --region $Region
  if ($LASTEXITCODE -ne 0) { throw "wait function-updated failed for $fn" }
  $cfg = aws lambda get-function-configuration --function-name $fn --region $Region --output json | ConvertFrom-Json
  [pscustomobject]@{
    function = $fn; state = $cfg.State; last_update = $cfg.LastUpdateStatus
    code_sha256_matches = ($cfg.CodeSha256 -eq $localB64); code_size = $cfg.CodeSize
  }
}
$results | Format-Table -AutoSize
if ($results | Where-Object { -not $_.code_sha256_matches -or $_.last_update -ne "Successful" }) { throw "Deployment verification failed" }
