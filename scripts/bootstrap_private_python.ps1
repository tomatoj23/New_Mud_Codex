[CmdletBinding()]
param(
    [string]$PythonSelector = "3.14"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$metadataText = & py "-$PythonSelector" -X utf8 -c `
    "import json, sys; print(json.dumps({'base_prefix': sys.base_prefix, 'version': list(sys.version_info[:3])}))"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to locate Python $PythonSelector through the Windows py launcher."
}

$metadata = $metadataText | ConvertFrom-Json
$version = ($metadata.version -join ".")
if ($metadata.version[0] -ne 3 -or $metadata.version[1] -ne 14) {
    throw "Python 3.14 is required; found $version."
}

$sourceRoot = (Resolve-Path -LiteralPath $metadata.base_prefix).Path
$buildRoot = Join-Path $repositoryRoot ".venv-build"
$runtimeRoot = Join-Path $buildRoot "runtime"
$venvRoot = Join-Path $repositoryRoot ".venv"
$backupRoot = Join-Path $repositoryRoot ".bootstrap-venv"

if (Test-Path -LiteralPath $buildRoot) {
    throw "$buildRoot already exists. Move it aside before retrying."
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$excludedDirectories = @(
    (Join-Path $sourceRoot "Doc"),
    (Join-Path $sourceRoot "Scripts"),
    (Join-Path $sourceRoot "Lib\site-packages")
)
$copyArguments = @(
    $sourceRoot,
    $runtimeRoot,
    "/E",
    "/COPY:DAT",
    "/DCOPY:DAT",
    "/R:2",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD"
) + $excludedDirectories

& robocopy @copyArguments | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "Failed to copy the private CPython runtime; robocopy exit code $LASTEXITCODE."
}

$stagedPython = Join-Path $runtimeRoot "python.exe"
& $stagedPython -I -c "import ensurepip, venv; print('private runtime ready')"
if ($LASTEXITCODE -ne 0) {
    throw "The copied CPython runtime is incomplete."
}

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$previousVenv = Join-Path $backupRoot "previous-$timestamp"
$failedVenv = Join-Path $backupRoot "failed-$timestamp"
$hadPreviousVenv = Test-Path -LiteralPath $venvRoot

if ($hadPreviousVenv) {
    Move-Item -LiteralPath $venvRoot -Destination $previousVenv
}
Move-Item -LiteralPath $buildRoot -Destination $venvRoot

try {
    $privateBasePython = Join-Path $venvRoot "runtime\python.exe"
    & $privateBasePython -m venv --copies $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the private virtual environment."
    }

    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    & $venvPython -m pip install --disable-pip-version-check --upgrade `
        "pip==26.1.2" "setuptools==83.0.0" "wheel==0.47.0"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install the project packaging toolchain."
    }

    & $venvPython -m pip install --disable-pip-version-check `
        -r (Join-Path $repositoryRoot "requirements.lock")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install project dependencies."
    }

    & $venvPython -m pip install --disable-pip-version-check --no-deps `
        --no-build-isolation `
        -e "${repositoryRoot}[dev]"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install the project package."
    }

    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) {
        throw "The private environment has dependency conflicts."
    }

    & $venvPython (Join-Path $repositoryRoot "scripts\verify_m0.py") --structural-only
    if ($LASTEXITCODE -ne 0) {
        throw "The private environment failed the M0 structural gate."
    }
}
catch {
    if (Test-Path -LiteralPath $venvRoot) {
        Move-Item -LiteralPath $venvRoot -Destination $failedVenv
    }
    if ($hadPreviousVenv -and (Test-Path -LiteralPath $previousVenv)) {
        Move-Item -LiteralPath $previousVenv -Destination $venvRoot
    }
    throw
}

Write-Output "Private Python $version environment ready at $venvRoot"
if ($hadPreviousVenv) {
    Write-Output "Previous environment retained at $previousVenv"
}
