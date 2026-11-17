[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$clientRoot = Join-Path $packageRoot 'tools\postgresql-client'
$runtimeRoot = Join-Path $clientRoot 'runtime'
$archive = Join-Path $clientRoot 'postgresql-18.6-5-windows-x64-binaries.zip'
$version = '18.6-5'
$baseUrl = "https://get.enterprisedb.com/postgresql/postgresql-$version-windows-x64-binaries.zip"
$expectedText = (Invoke-WebRequest -Uri "$baseUrl.sha256" -TimeoutSec 60).Content
$expectedMatch = [regex]::Match($expectedText, '(?i)\b([a-f0-9]{64})\b')
if (-not $expectedMatch.Success) { throw 'The official EDB SHA-256 sidecar did not contain a digest.' }
$expectedHash = $expectedMatch.Groups[1].Value.ToLowerInvariant()

if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    Invoke-WebRequest -Uri $baseUrl -OutFile $archive -TimeoutSec 900
}
$actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) { throw 'PostgreSQL binaries archive SHA-256 does not match the EDB sidecar.' }

$binEntries = @(
    'pgsql/bin/pg_dump.exe', 'pgsql/bin/pg_restore.exe', 'pgsql/bin/psql.exe',
    'pgsql/bin/icudt77.dll', 'pgsql/bin/icuin77.dll', 'pgsql/bin/icuio77.dll', 'pgsql/bin/icutu77.dll', 'pgsql/bin/icuuc77.dll',
    'pgsql/bin/libcrypto-3-x64.dll', 'pgsql/bin/libcurl.dll', 'pgsql/bin/libecpg_compat.dll', 'pgsql/bin/libecpg.dll',
    'pgsql/bin/libiconv-2.dll', 'pgsql/bin/libintl-9.dll', 'pgsql/bin/liblz4.dll', 'pgsql/bin/libpgtypes.dll', 'pgsql/bin/libpq.dll',
    'pgsql/bin/libssl-3-x64.dll', 'pgsql/bin/libwinpthread-1.dll', 'pgsql/bin/libxml2.dll', 'pgsql/bin/libxslt.dll',
    'pgsql/bin/libzstd.dll', 'pgsql/bin/testplug.dll', 'pgsql/bin/wxbase3211u_net_vc_x64_custom.dll',
    'pgsql/bin/wxbase3211u_vc_x64_custom.dll', 'pgsql/bin/wxbase3211u_xml_vc_x64_custom.dll',
    'pgsql/bin/wxmsw3211u_adv_vc_x64_custom.dll', 'pgsql/bin/wxmsw3211u_aui_vc_x64_custom.dll',
    'pgsql/bin/wxmsw3211u_core_vc_x64_custom.dll', 'pgsql/bin/wxmsw3211u_html_vc_x64_custom.dll',
    'pgsql/bin/wxmsw3211u_xrc_vc_x64_custom.dll', 'pgsql/bin/zlib1.dll'
)
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
tar.exe -xf $archive -C $runtimeRoot @binEntries
if ($LASTEXITCODE -ne 0) { throw "tar extraction failed with exit code $LASTEXITCODE." }

$pgDump = Join-Path $runtimeRoot 'pgsql\bin\pg_dump.exe'
$pgRestore = Join-Path $runtimeRoot 'pgsql\bin\pg_restore.exe'
$dumpVersion = (& $pgDump --version).Trim()
$restoreVersion = (& $pgRestore --version).Trim()
if ($LASTEXITCODE -ne 0 -or $dumpVersion -notmatch 'PostgreSQL\) 18\.6$' -or $restoreVersion -notmatch 'PostgreSQL\) 18\.6$') {
    throw 'The package-local pg_dump/pg_restore executables failed their version check.'
}

$manifest = [ordered]@{
    version = '18.6'
    release = $version
    source = $baseUrl
    checksum_source = "$baseUrl.sha256"
    archive_sha256 = $actualHash
    pg_dump_version = $dumpVersion
    pg_restore_version = $restoreVersion
    extracted_files = $binEntries
    prepared_at_utc = [DateTime]::UtcNow.ToString('o')
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $clientRoot 'client-manifest.json') -Encoding utf8
Write-Output ($manifest | ConvertTo-Json -Depth 5)
