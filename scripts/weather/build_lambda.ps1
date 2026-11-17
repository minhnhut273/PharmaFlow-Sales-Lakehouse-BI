<#
.SYNOPSIS
  Build the weather Lambda zip (.runtime/weather/weather_lambda.zip) for python3.12 x86_64.

.DESCRIPTION
  Installs Linux wheels (manylinux2014_x86_64, CPython 3.12) from scripts/weather/lambda-requirements.txt,
  copies src/weather (without caches/docs), zips the result, and prints size + SHA-256.
  Uses the project .venv only for pip; never packages the Windows .venv.
#>
[CmdletBinding()]
param(
  [string]$RepoRoot = ""
)
$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$req = Join-Path $PSScriptRoot "lambda-requirements.txt"
$outDir = Join-Path $RepoRoot ".runtime\weather"
$build = Join-Path $outDir "build"
$zip = Join-Path $outDir "weather_lambda.zip"
$maxZipBytes = 50MB

if (-not (Test-Path $python)) { throw "Missing $python (project .venv)" }
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force -Path $build | Out-Null

& $python -B -m pip install --disable-pip-version-check --quiet `
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --abi cp312 `
  --only-binary=:all: --target $build -r $req
if ($LASTEXITCODE -ne 0) { throw "pip install for Lambda failed" }

# Application code: src/weather only (namespace package `src`, no __init__.py needed).
$dst = Join-Path $build "src\weather"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Get-ChildItem -Path (Join-Path $RepoRoot "src\weather") -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\__pycache__\\' -and $_.Extension -in '.py', '.yaml' } |
  ForEach-Object {
    $rel = $_.FullName.Substring((Join-Path $RepoRoot "src\weather").Length + 1)
    $target = Join-Path $dst $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    Copy-Item $_.FullName $target
  }

# Drop caches, tests shipped inside wheels, and host-specific console-script launchers (bin/*.exe).
$binDir = Join-Path $build "bin"
if (Test-Path $binDir) { Remove-Item -Recurse -Force $binDir }
Get-ChildItem -Path $build -Recurse -Directory -Include "__pycache__", "tests" -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\src\\weather\\' } | Remove-Item -Recurse -Force

if (Test-Path $zip) { Remove-Item -Force $zip }
& $python -B -c @"
import os, sys, zipfile
root, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            arc = os.path.relpath(path, root).replace(os.sep, '/')
            info = zipfile.ZipInfo(arc, date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(path, 'rb') as fh:
                z.writestr(info, fh.read())
"@ $build $zip
if ($LASTEXITCODE -ne 0) { throw "zip failed" }

$size = (Get-Item $zip).Length
$sha = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
$b64 = & $python -B -c "import base64,hashlib,sys;print(base64.b64encode(hashlib.sha256(open(sys.argv[1],'rb').read()).digest()).decode())" $zip
if ($size -gt $maxZipBytes) { throw "Zip is $size bytes (> 50 MB direct-upload limit)" }
Remove-Item -Recurse -Force $build
[pscustomobject]@{ zip = $zip; bytes = $size; sha256 = $sha; code_sha256_b64 = $b64 } | Format-List
