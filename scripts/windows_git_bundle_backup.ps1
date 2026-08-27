#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RepositoryUrl = 'https://github.com/tomatoj23/New_Mud_Linux.git',

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$BackupRoot = 'D:\New_Mud_Backups',

    [Parameter()]
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedRepositoryUrl = 'https://github.com/tomatoj23/New_Mud_Linux.git'

function Invoke-GitCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    $previousErrorPreference = $ErrorActionPreference
    try {
        # Windows PowerShell turns native stderr into ErrorRecord objects.
        # Keep collecting those records so the native exit code remains the
        # single success/failure authority for this wrapper.
        $ErrorActionPreference = 'Continue'
        $commandOutput = @(& git @Arguments 2>&1)
        $commandExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }
    if ($commandExitCode -ne 0) {
        $renderedArguments = $Arguments -join ' '
        $renderedOutput = $commandOutput -join [Environment]::NewLine
        throw "git command failed with exit code ${commandExitCode}: git ${renderedArguments}`n${renderedOutput}"
    }
    return $commandOutput
}

function Write-Utf8WithoutBom {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$LiteralPath,

        [Parameter(Mandatory)]
        [string]$Content
    )

    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($LiteralPath, $Content, $utf8WithoutBom)
}

if ($RepositoryUrl -ne $ExpectedRepositoryUrl) {
    throw "RepositoryUrl must remain exactly ${ExpectedRepositoryUrl}. Refusing alternate target: ${RepositoryUrl}"
}

$gitCommand = Get-Command git -CommandType Application -ErrorAction Stop
$resolvedBackupRoot = [System.IO.Path]::GetFullPath($BackupRoot)
$backupVolumeRoot = [System.IO.Path]::GetPathRoot($resolvedBackupRoot)
if ($resolvedBackupRoot.TrimEnd('\') -eq $backupVolumeRoot.TrimEnd('\')) {
    throw "BackupRoot must be a dedicated directory, not a volume root: ${resolvedBackupRoot}"
}

$remoteMainOutput = @(Invoke-GitCommand -Arguments @(
    'ls-remote',
    '--exit-code',
    $RepositoryUrl,
    'refs/heads/main'
))
$remoteMainLines = @($remoteMainOutput | Where-Object {
    [string]$_ -match '^[0-9a-f]{40,64}\s+refs/heads/main$'
})
if ($remoteMainLines.Count -ne 1) {
    throw 'The target repository did not return exactly one refs/heads/main line.'
}
$remoteMainFields = ([string]$remoteMainLines[0]) -split '\s+'
if ($remoteMainFields.Count -lt 2 -or $remoteMainFields[1] -ne 'refs/heads/main') {
    throw 'The target repository did not return exactly refs/heads/main.'
}
$remoteMainSha = $remoteMainFields[0]
if ($remoteMainSha -notmatch '^[0-9a-f]{40,64}$') {
    throw "The remote main SHA is not valid: ${remoteMainSha}"
}

if ($ValidateOnly) {
    [pscustomobject]@{
        status = 'success'
        validation_only = $true
        repository = $RepositoryUrl
        remote_main = $remoteMainSha
        backup_root = $resolvedBackupRoot
        git = $gitCommand.Source
        writes_performed = $false
    } | ConvertTo-Json
    return
}

$mirrorParent = Join-Path $resolvedBackupRoot 'mirror'
$mirrorPath = Join-Path $mirrorParent 'New_Mud_Linux.git'
$bundlePath = Join-Path $resolvedBackupRoot 'bundles'

New-Item -ItemType Directory -Path $mirrorParent -Force | Out-Null
New-Item -ItemType Directory -Path $bundlePath -Force | Out-Null

if (-not (Test-Path -LiteralPath $mirrorPath)) {
    Invoke-GitCommand -Arguments @('clone', '--mirror', $RepositoryUrl, $mirrorPath) | Out-Null
}

$isBareOutput = @(Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'rev-parse', '--is-bare-repository'
))
$isBare = $isBareOutput[-1]
if ($isBare -ne 'true') {
    throw "Backup mirror is not a bare repository: ${mirrorPath}"
}

$configuredRemoteOutput = @(Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'config', '--get', 'remote.origin.url'
))
$configuredRemote = $configuredRemoteOutput[-1]
if ($configuredRemote -ne $RepositoryUrl) {
    throw "Existing mirror origin differs from the fixed repository. Expected ${RepositoryUrl}; got ${configuredRemote}"
}

# Convert clone --mirror's forced refspec into a non-forcing, non-pruning fetch.
# This makes a remote history rewrite or deletion a hard failure instead of
# silently copying it over the local backup reference.
Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'config', 'remote.origin.mirror', 'false'
) | Out-Null
Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'config', '--replace-all',
    'remote.origin.fetch', 'refs/heads/*:refs/heads/*'
) | Out-Null

Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'fetch', '--no-force', '--tags',
    'origin', 'refs/heads/*:refs/heads/*'
) | Out-Null

$localMainOutput = @(Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'rev-parse', 'refs/heads/main'
))
$localMainSha = $localMainOutput[-1]
if ($localMainSha -ne $remoteMainSha) {
    throw "Fetched main does not match GitHub. Remote ${remoteMainSha}; local ${localMainSha}"
}

Invoke-GitCommand -Arguments @('-C', $mirrorPath, 'fsck', '--full', '--strict') | Out-Null

$utcNow = [DateTime]::UtcNow
$timestamp = $utcNow.ToString('yyyyMMddTHHmmssfffZ')
$shortSha = $localMainSha.Substring(0, 12)
$bundleBaseName = "New_Mud_Linux-full-${timestamp}-${shortSha}"
$bundleFile = Join-Path $bundlePath "${bundleBaseName}.bundle"
$shaFile = Join-Path $bundlePath "${bundleBaseName}.sha256"
$metadataFile = Join-Path $bundlePath "${bundleBaseName}.json"

Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'bundle', 'create', $bundleFile, '--all'
) | Out-Null
$bundleVerifyOutput = Invoke-GitCommand -Arguments @(
    '-C', $mirrorPath, 'bundle', 'verify', $bundleFile
)

$bundleHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $bundleFile).Hash.ToLowerInvariant()
$bundleLength = (Get-Item -LiteralPath $bundleFile).Length
$shaLine = "${bundleHash}  $([System.IO.Path]::GetFileName($bundleFile))`n"
Write-Utf8WithoutBom -LiteralPath $shaFile -Content $shaLine

$referenceOutput = Invoke-GitCommand -Arguments @('-C', $mirrorPath, 'show-ref')
$references = foreach ($line in $referenceOutput) {
    $fields = ([string]$line) -split '\s+', 2
    if ($fields.Count -eq 2) {
        [ordered]@{
            sha = $fields[0]
            ref = $fields[1]
        }
    }
}

$gitVersionOutput = @(Invoke-GitCommand -Arguments @('--version'))
$gitVersion = $gitVersionOutput[-1]
$metadata = [ordered]@{
    schema_version = 1
    created_utc = $utcNow.ToString('o')
    repository = $RepositoryUrl
    fetch_mode = 'non-force, no-prune, fetch-only'
    remote_main = $remoteMainSha
    mirror_main = $localMainSha
    mirror_path = $mirrorPath
    bundle_file = [System.IO.Path]::GetFileName($bundleFile)
    bundle_bytes = $bundleLength
    bundle_sha256 = $bundleHash
    sha256_file = [System.IO.Path]::GetFileName($shaFile)
    git_version = $gitVersion
    fsck = 'passed --full --strict'
    bundle_verify = 'passed'
    bundle_verify_output = @($bundleVerifyOutput | ForEach-Object { [string]$_ })
    references = @($references)
    automatic_deletion = $false
}
Write-Utf8WithoutBom -LiteralPath $metadataFile -Content (($metadata | ConvertTo-Json -Depth 8) + "`n")

[pscustomobject]@{
    status = 'success'
    validation_only = $false
    repository = $RepositoryUrl
    remote_main = $remoteMainSha
    mirror = $mirrorPath
    bundle = $bundleFile
    sha256 = $bundleHash
    sha256_file = $shaFile
    metadata_file = $metadataFile
    fsck = 'passed'
    bundle_verify = 'passed'
    automatic_deletion = $false
} | ConvertTo-Json
