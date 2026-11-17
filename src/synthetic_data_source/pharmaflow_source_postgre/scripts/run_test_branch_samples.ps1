[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
throw @"
The isolated Neon test branch was retired and deleted after its 7/7 acceptance run.
This project is configured for one active environment only: production / pharmaflow_source_postgre_v2.
Historical sample outputs remain under runs\20261104-forecast-schema-v2\test\forecast-validation-20261104.
No URL was requested and no database connection was attempted.
"@
