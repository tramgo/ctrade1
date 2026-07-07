param(
    [string] $AcrName = "HeldC1",
    [string] $Repository = "zerodha-12-c011ector",
    [string] $Tag = "",
    [switch] $SkipLatest,
    [switch] $UseAcrBuild
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
}

function Invoke-Az {
    if (-not [string]::IsNullOrWhiteSpace($env:AZURE_CLI_PYTHON_EXE)) {
        & $env:AZURE_CLI_PYTHON_EXE -m azure.cli @args
    } else {
        & az @args
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI failed with exit code ${LASTEXITCODE}: az $($args -join ' ')"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$collectorRoot = Join-Path $repoRoot "zerodha_equity_collector"
if ([string]::IsNullOrWhiteSpace($Tag)) {
    $Tag = (Get-Date -Format "yyyyMMdd-HHmmss")
}

$loginServer = Invoke-Az acr show --name $AcrName --query loginServer -o tsv
if ([string]::IsNullOrWhiteSpace($loginServer)) {
    throw "Could not resolve ACR login server for $AcrName."
}

$imagePinned = "${loginServer}/${Repository}:${Tag}"
$imageLatest = "${loginServer}/${Repository}:latest"

if ($UseAcrBuild) {
    $acrBuildArgs = @(
        "acr", "build",
        "--registry", $AcrName,
        "--file", (Join-Path $collectorRoot "Dockerfile"),
        "--image", "${Repository}:${Tag}"
    )
    if (-not $SkipLatest) {
        $acrBuildArgs += @("--image", "${Repository}:latest")
    }
    $acrBuildArgs += $collectorRoot
    Invoke-Az @acrBuildArgs
} else {
    Invoke-Az acr login --name $AcrName

    $buildArgs = @(
        "build",
        "--file", (Join-Path $collectorRoot "Dockerfile"),
        "--tag", $imagePinned
    )
    if (-not $SkipLatest) {
        $buildArgs += @("--tag", $imageLatest)
    }
    $buildArgs += $collectorRoot

    & docker @buildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker build failed with exit code $LASTEXITCODE. If Docker Desktop Linux cannot start, rerun with -UseAcrBuild."
    }

    & docker push $imagePinned
    if ($LASTEXITCODE -ne 0) {
        throw "docker push failed for $imagePinned"
    }

    if (-not $SkipLatest) {
        & docker push $imageLatest
        if ($LASTEXITCODE -ne 0) {
            throw "docker push failed for $imageLatest"
        }
    }
}

Write-Host "Pinned image: $imagePinned"
if (-not $SkipLatest) {
    Write-Host "Latest image: $imageLatest"
}
