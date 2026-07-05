param(
    [string] $SubscriptionId = "0896829f-ea22-46cd-ae31-02ab40195c2c",
    [string] $ResourceGroup = "MyRG",
    [string] $Location = "southindia",
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
    [string] $GeneratedOutputPaths = "results data"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$imageName = "${AcrName}.azurecr.io/ctrade1/${ImageTag}:latest"
$envPath = Join-Path $repoRoot $EnvFile

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

az account set --subscription $SubscriptionId
az group create --name $ResourceGroup --location $Location | Out-Null
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait

az acr create `
  --resource-group $ResourceGroup `
  --name $AcrName `
  --sku Basic `
  --admin-enabled true | Out-Null

$acrUser = az acr credential show `
  --name $AcrName `
  --query username `
  --output tsv

$acrPassword = az acr credential show `
  --name $AcrName `
  --query "passwords[0].value" `
  --output tsv

az acr build `
  --registry $AcrName `
  --image "ctrade1/${ImageTag}:latest" `
  --file (Join-Path $repoRoot "azure_scheduled_jobs\Dockerfile") `
  $repoRoot

az monitor log-analytics workspace create `
  --resource-group $ResourceGroup `
  --workspace-name $LogAnalyticsName `
  --location $Location | Out-Null

$workspaceId = az monitor log-analytics workspace show `
  --resource-group $ResourceGroup `
  --workspace-name $LogAnalyticsName `
  --query customerId `
  --output tsv

$workspaceKey = az monitor log-analytics workspace get-shared-keys `
  --resource-group $ResourceGroup `
  --workspace-name $LogAnalyticsName `
  --query primarySharedKey `
  --output tsv

az containerapp env create `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --location $Location `
  --logs-workspace-id $workspaceId `
  --logs-workspace-key $workspaceKey | Out-Null

az storage account create `
  --resource-group $ResourceGroup `
  --name $StorageAccountName `
  --location $Location `
  --sku Standard_LRS | Out-Null

$storageKey = az storage account keys list `
  --resource-group $ResourceGroup `
  --account-name $StorageAccountName `
  --query "[0].value" `
  --output tsv

$resultsShareName = "${FileShareName}results"
$dataShareName = "${FileShareName}data"

az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $resultsShareName `
  --quota 20 | Out-Null

az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $dataShareName `
  --quota 20 | Out-Null

az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name ctrade1results `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $resultsShareName `
  --access-mode ReadWrite | Out-Null

az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name ctrade1data `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $dataShareName `
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
        Replace("__ACR_SERVER__", "${AcrName}.azurecr.io").
        Replace("__ACR_USERNAME__", $acrUser).
        Replace("__ACR_PASSWORD__", $acrPassword).
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
        Replace("__IMAGE__", $imageName).
        Replace("__CRON__", $job.Cron).
        Replace("__JOB_KIND__", $job.Kind)

    $yamlPath = Join-Path $env:TEMP "$($job.Name).containerapp-job.yaml"
    Set-Content -Path $yamlPath -Value $yaml -Encoding UTF8

    az containerapp job create `
      --name $job.Name `
      --resource-group $ResourceGroup `
      --yaml $yamlPath | Out-Null
}

Write-Host "Created Azure Container Apps jobs:"
$jobs | ForEach-Object { Write-Host " - $($_.Name) cron=$($_.Cron) kind=$($_.Kind)" }
Write-Host "Resource group: $ResourceGroup"
Write-Host "Location: $Location"
Write-Host "Azure Files shares: $resultsShareName, $dataShareName"
Write-Host "GitHub output push enabled: $($EnableGitHubOutputPush.IsPresent)"
Write-Host "Run a smoke execution with:"
Write-Host "az containerapp job start --name tb11-phase1-0940 --resource-group $ResourceGroup"
