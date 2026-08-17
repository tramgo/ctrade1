param(
    [string] $SubscriptionId = "0896829f-ea22-46cd-ae31-02ab40195c2c",
    [string] $ResourceGroup = "MyRG",
    [string] $Location = "eastus2",
    [Parameter(Mandatory = $true)] [string] $AcrName,
    [Parameter(Mandatory = $true)] [string] $EnvironmentName,
    [Parameter(Mandatory = $true)] [string] $LogAnalyticsName,
    [Parameter(Mandatory = $true)] [string] $StorageAccountName,
    [Parameter(Mandatory = $true)] [string] $FileShareName,
    [string] $ImageTag = "tb11-jobs",
    [string] $EnvFile = ".env",
    [switch] $EnableGitHubOutputPush,
    [string] $GitHubRepoUrl = "https://github.com/tramgo/ctrade1.git",
    [string] $GitHubBranch = "main",
    [string] $GeneratedOutputPaths = "results data",
    [int] $LogRetentionDays = 3,
    [int] $LogRetentionMinFiles = 6,
    [string] $IdentityName = "id-ctrade1-jobs",
    [string] $KiteTokenShareName = "ctrade1-kite-token",
    [string] $KiteTokenStorageName = "ctrade1kitetoken"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envPath = Join-Path $repoRoot $EnvFile

function New-SanitizedBuildContext {
    param([string] $SourceRoot)

    $buildRoot = Join-Path $env:TEMP ("ctrade1_azure_build_" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force $buildRoot | Out-Null

    $excludePrefixes = @(
        "data/",
        "plots/",
        "results/",
        "results1/",
        "results2/",
        "results3/",
        "results4/",
        "results5/",
        "results6_m1/",
        "tensorboard_logs/",
        "tensorboard_logs1/",
        "tensorboard_logs2/",
        "tensorboard_logs3/",
        "tensorboard_logs4/",
        "tensorboard_logs5/",
        "tensorboard_logs6_m1/"
    )
    $excludeExact = @(
        ".env",
        ".env.example",
        "access_token_cache.txt",
        "optuna_study.db"
    )

    $trackedFiles = & git -C $SourceRoot ls-files
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed while creating sanitized Azure build context."
    }

    foreach ($relativePath in $trackedFiles) {
        $normalized = $relativePath.Replace("\", "/")
        if ($excludeExact -contains $normalized) {
            continue
        }
        $skip = $false
        foreach ($prefix in $excludePrefixes) {
            if ($normalized.StartsWith($prefix)) {
                $skip = $true
                break
            }
        }
        if ($skip) {
            continue
        }

        $sourcePath = Join-Path $SourceRoot $relativePath
        $targetPath = Join-Path $buildRoot $relativePath
        $targetDir = Split-Path -Parent $targetPath
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Force $targetDir | Out-Null
        }
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
    }

    $azureTarget = Join-Path $buildRoot "azure_scheduled_jobs"
    Remove-Item -LiteralPath $azureTarget -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item `
      -LiteralPath (Join-Path $SourceRoot "azure_scheduled_jobs") `
      -Destination $azureTarget `
      -Recurse `
      -Force

    return $buildRoot
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

function Read-DotEnvFile {
    param([string] $Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        throw "Env file not found: $Path"
    }

    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*$' -or $line -match '^\s*#') {
            continue
        }

        $parts = $line -split '=', 2
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }

    return $values
}

$envValues = Read-DotEnvFile -Path $envPath
if ($LogRetentionDays -lt 1) {
    throw "LogRetentionDays must be at least 1."
}
if ($LogRetentionMinFiles -lt 1) {
    throw "LogRetentionMinFiles must be at least 1."
}
$requiredEnvKeys = @("API_KEY", "API_SECRET", "USERNAME", "PASSWORD", "TOTP_KEY")
foreach ($key in $requiredEnvKeys) {
    if (-not $envValues.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envValues[$key])) {
        throw "Required .env key is missing or empty: $key"
    }
}

$githubToken = ""
if ($envValues.ContainsKey("GITHUB_TOKEN")) {
    $githubToken = $envValues["GITHUB_TOKEN"]
} elseif ($envValues.ContainsKey("GH_TOKEN")) {
    $githubToken = $envValues["GH_TOKEN"]
}

if ($EnableGitHubOutputPush -and [string]::IsNullOrWhiteSpace($githubToken)) {
    throw "GitHub output push requested, but .env has no GITHUB_TOKEN or GH_TOKEN. Add a fine-grained token with contents read/write for tramgo/ctrade1."
}
$githubTokenSecretValue = if ([string]::IsNullOrWhiteSpace($githubToken)) { "unused" } else { $githubToken }

Invoke-Az account set --subscription $SubscriptionId
$groupExists = (Invoke-Az group exists --name $ResourceGroup --output tsv).Trim()
if ($groupExists -ne "true") {
  Invoke-Az group create --name $ResourceGroup --location $Location | Out-Null
}
Invoke-Az provider register --namespace Microsoft.App --wait
Invoke-Az provider register --namespace Microsoft.OperationalInsights --wait

$acr = Invoke-Az acr show `
  --resource-group $ResourceGroup `
  --name $AcrName `
  --query "{id:id, loginServer:loginServer}" `
  --output json | ConvertFrom-Json
$acrId = $acr.id
$imageName = "$($acr.loginServer)/ctrade1/${ImageTag}:latest"
$buildContext = New-SanitizedBuildContext -SourceRoot $repoRoot

$identity = Invoke-Az identity create `
  --name $IdentityName `
  --resource-group $ResourceGroup `
  --location $Location `
  --query "{id:id, principalId:principalId}" `
  --output json | ConvertFrom-Json

$existingAcrPullAssignments = Invoke-Az role assignment list `
  --assignee $identity.principalId `
  --role AcrPull `
  --scope $acrId `
  --query "[].id" `
  --output tsv

if ([string]::IsNullOrWhiteSpace($existingAcrPullAssignments)) {
    Invoke-Az role assignment create `
      --assignee $identity.principalId `
      --role AcrPull `
      --scope $acrId | Out-Null
}

Invoke-Az acr build `
  --registry $AcrName `
  --image "ctrade1/${ImageTag}:latest" `
  --file (Join-Path $buildContext "azure_scheduled_jobs\Dockerfile") `
  --no-logs `
  $buildContext

Invoke-Az monitor log-analytics workspace create `
  --resource-group $ResourceGroup `
  --workspace-name $LogAnalyticsName `
  --location $Location | Out-Null

$workspaceId = Invoke-Az monitor log-analytics workspace show `
  --resource-group $ResourceGroup `
  --workspace-name $LogAnalyticsName `
  --query customerId `
  --output tsv

$workspaceKey = Invoke-Az monitor log-analytics workspace get-shared-keys `
  --resource-group $ResourceGroup `
  --workspace-name $LogAnalyticsName `
  --query primarySharedKey `
  --output tsv

Invoke-Az containerapp env create `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --location $Location `
  --logs-workspace-id $workspaceId `
  --logs-workspace-key $workspaceKey | Out-Null

Invoke-Az storage account create `
  --resource-group $ResourceGroup `
  --name $StorageAccountName `
  --location $Location `
  --sku Standard_LRS | Out-Null

$storageKey = Invoke-Az storage account keys list `
  --resource-group $ResourceGroup `
  --account-name $StorageAccountName `
  --query "[0].value" `
  --output tsv

$resultsShareName = "${FileShareName}results"
$dataShareName = "${FileShareName}data"

Invoke-Az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $resultsShareName `
  --quota 102400 | Out-Null

Invoke-Az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $dataShareName `
  --quota 102400 | Out-Null

Invoke-Az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $KiteTokenShareName `
  --quota 1 `
  --access-tier TransactionOptimized | Out-Null

$storageAccountId = Invoke-Az storage account show `
  --resource-group $ResourceGroup `
  --name $StorageAccountName `
  --query id `
  --output tsv

$kiteTokenShareScope = "${storageAccountId}/fileServices/default/shares/${KiteTokenShareName}"
$existingKiteTokenAssignments = Invoke-Az role assignment list `
  --assignee $identity.principalId `
  --role "Storage File Data SMB Share Contributor" `
  --scope $kiteTokenShareScope `
  --query "[].id" `
  --output tsv

if ([string]::IsNullOrWhiteSpace($existingKiteTokenAssignments)) {
    Invoke-Az role assignment create `
      --assignee $identity.principalId `
      --role "Storage File Data SMB Share Contributor" `
      --scope $kiteTokenShareScope | Out-Null
}

Invoke-Az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name ctrade1results `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $resultsShareName `
  --access-mode ReadWrite | Out-Null

Invoke-Az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name ctrade1data `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $dataShareName `
  --access-mode ReadWrite | Out-Null

Invoke-Az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name $KiteTokenStorageName `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $KiteTokenShareName `
  --access-mode ReadWrite | Out-Null

$yamlTemplate = Get-Content (Join-Path $repoRoot "azure_scheduled_jobs\infra\containerapp-job.template.yaml") -Raw
$environmentId = "/subscriptions/${SubscriptionId}/resourceGroups/${ResourceGroup}/providers/Microsoft.App/managedEnvironments/${EnvironmentName}"

$jobs = @(
    @{ Name = "tb11-phase1-0940"; Cron = "10 4 * * 1-5"; Kind = "phase1" },
    @{ Name = "tb11-t28-0945"; Cron = "15 4 * * 1-5"; Kind = "t28" },
    @{ Name = "tb11-phase1-1230"; Cron = "0 7 * * 1-5"; Kind = "phase1" },
    @{ Name = "tb11-phase1-1445"; Cron = "15 9 * * 1-5"; Kind = "phase1" }
)

foreach ($job in $jobs) {
    $yaml = $yamlTemplate.
        Replace("__JOB_NAME__", $job.Name).
        Replace("__LOCATION__", $Location).
        Replace("__ENVIRONMENT_ID__", $environmentId).
        Replace("__USER_ASSIGNED_IDENTITY_ID__", $identity.id).
        Replace("__ACR_SERVER__", $acr.loginServer).
        Replace("__API_KEY__", $envValues["API_KEY"]).
        Replace("__API_SECRET__", $envValues["API_SECRET"]).
        Replace("__USERNAME__", $envValues["USERNAME"]).
        Replace("__PASSWORD__", $envValues["PASSWORD"]).
        Replace("__TOTP_KEY__", $envValues["TOTP_KEY"]).
        Replace("__GITHUB_TOKEN__", $githubTokenSecretValue).
        Replace("__GITHUB_OUTPUT_PUSH_ENABLED__", $(if ($EnableGitHubOutputPush) { "1" } else { "0" })).
        Replace("__GITHUB_REPO_URL__", $GitHubRepoUrl).
        Replace("__GITHUB_BRANCH__", $GitHubBranch).
        Replace("__GENERATED_OUTPUT_PATHS__", $GeneratedOutputPaths).
        Replace("__LOG_RETENTION_DAYS__", [string]$LogRetentionDays).
        Replace("__LOG_RETENTION_MIN_FILES__", [string]$LogRetentionMinFiles).
        Replace("__IMAGE__", $imageName).
        Replace("__CRON__", $job.Cron).
        Replace("__JOB_KIND__", $job.Kind)

    $yamlPath = Join-Path $env:TEMP "$($job.Name).containerapp-job.yaml"
    Set-Content -Path $yamlPath -Value $yaml -Encoding UTF8

    $jobExists = $false
    try {
        Invoke-Az containerapp job show `
          --name $job.Name `
          --resource-group $ResourceGroup `
          --query name `
          --output tsv | Out-Null
        $jobExists = $true
    } catch {
        $jobExists = $false
    }

    if ($jobExists) {
        Invoke-Az containerapp job delete `
          --name $job.Name `
          --resource-group $ResourceGroup `
          --yes | Out-Null
    }

    try {
        Invoke-Az containerapp job create `
          --name $job.Name `
          --resource-group $ResourceGroup `
          --yaml $yamlPath | Out-Null
    } finally {
        Remove-Item -LiteralPath $yamlPath -Force -ErrorAction SilentlyContinue
    }

}

Write-Host "Created Azure Container Apps jobs:"
$jobs | ForEach-Object { Write-Host " - $($_.Name) cron=$($_.Cron) kind=$($_.Kind)" }
Write-Host "Resource group: $ResourceGroup"
Write-Host "Location: $Location"
Write-Host "ACR: $AcrName"
Write-Host "Managed identity: $IdentityName"
Write-Host "Azure Files shares: $resultsShareName, $dataShareName, $KiteTokenShareName"
Write-Host "Container Apps token storage name: $KiteTokenStorageName"
Write-Host "GitHub output push enabled: $($EnableGitHubOutputPush.IsPresent)"
Write-Host "Run a smoke execution with:"
Write-Host "az containerapp job start --name tb11-phase1-0940 --resource-group $ResourceGroup"
