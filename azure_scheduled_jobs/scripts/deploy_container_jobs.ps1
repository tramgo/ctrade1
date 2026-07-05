param(
    [Parameter(Mandatory = $true)] [string] $SubscriptionId,
    [Parameter(Mandatory = $true)] [string] $ResourceGroup,
    [Parameter(Mandatory = $true)] [string] $Location,
    [Parameter(Mandatory = $true)] [string] $AcrName,
    [Parameter(Mandatory = $true)] [string] $EnvironmentName,
    [Parameter(Mandatory = $true)] [string] $LogAnalyticsName,
    [Parameter(Mandatory = $true)] [string] $StorageAccountName,
    [Parameter(Mandatory = $true)] [string] $FileShareName,
    [string] $ImageTag = "tb11-jobs"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$imageName = "${AcrName}.azurecr.io/ctrade1/${ImageTag}:latest"

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

az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $FileShareName `
  --quota 20 | Out-Null

az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name ctrade1state `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $FileShareName `
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
Write-Host "Run a smoke execution with:"
Write-Host "az containerapp job start --name tb11-phase1-0940 --resource-group $ResourceGroup"
