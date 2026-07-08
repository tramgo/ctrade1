param(
    [string] $ResourceGroup = "rg-12-c011ector-shakedown-cin",
    [string] $Location = "centralindia",
    [string] $AcrName = "HeldC1",
    [string] $Repository = "zerodha-12-c011ector",
    [Parameter(Mandatory = $true)] [string] $ImageTag,
    [string] $StorageAccountName = "st12c011ectorramic",
    [string] $StorageResourceGroup = "",
    [string] $BlobContainerName = "raw-12",
    [string] $FileShareName = "12-session",
    [string] $IdentityName = "id-12-c011ector",
    [string] $KeyVaultName = "kv-12-c011ector-ramic",
    [string] $ContainerName = "12-c011ector-manual",
    [ValidateSet("l2-live", "l2-audit", "l2-preflight", "l2-status")]
    [string] $CollectorMode = "l2-live",
    [double] $Cpu = 1,
    [double] $MemoryGb = 1,
    [switch] $AllowOutsideSession,
    [switch] $DeleteLocalAfterUpload
)

$ErrorActionPreference = "Stop"

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

$loginServer = Invoke-Az acr show --name $AcrName --query loginServer -o tsv
if ([string]::IsNullOrWhiteSpace($loginServer)) {
    throw "Could not resolve ACR login server for $AcrName."
}
$image = "${loginServer}/${Repository}:${ImageTag}"

$identity = Invoke-Az identity show --name $IdentityName --resource-group $ResourceGroup | ConvertFrom-Json
$identityId = $identity.id

if ([string]::IsNullOrWhiteSpace($StorageResourceGroup)) {
    $storage = Invoke-Az storage account show --name $StorageAccountName | ConvertFrom-Json
    $StorageResourceGroup = $storage.resourceGroup
}

$storageKey = Invoke-Az storage account keys list --account-name $StorageAccountName --resource-group $StorageResourceGroup --query "[0].value" -o tsv
if ([string]::IsNullOrWhiteSpace($storageKey)) {
    throw "Could not read storage account key for Azure Files mount."
}

$accountUrl = "https://${StorageAccountName}.blob.core.windows.net"
$allowOutside = if ($AllowOutsideSession) { "1" } else { "0" }
$deleteAfterUpload = if ($DeleteLocalAfterUpload) { "1" } else { "0" }

try {
    Invoke-Az container delete --resource-group $ResourceGroup --name $ContainerName --yes | Out-Null
} catch {
    Write-Host "No existing ACI named $ContainerName to delete."
}

Invoke-Az container create `
  --resource-group $ResourceGroup `
  --name $ContainerName `
  --image $image `
  --acr-identity $identityId `
  --assign-identity $identityId `
  --cpu $Cpu `
  --memory $MemoryGb `
  --os-type Linux `
  --restart-policy Never `
  --location $Location `
  --azure-file-volume-account-name $StorageAccountName `
  --azure-file-volume-account-key $storageKey `
  --azure-file-volume-share-name $FileShareName `
  --azure-file-volume-mount-path /data `
  --environment-variables `
    KEY_VAULT_NAME=$KeyVaultName `
    COLLECTOR_MODE=$CollectorMode `
    COLLECTOR_DATA_ROOT=/data `
    AZURE_STORAGE_ACCOUNT_URL=$accountUrl `
    AZURE_STORAGE_CONTAINER=$BlobContainerName `
    AZURE_BLOB_PREFIX= `
    AZURE_UPLOAD_AFTER_RUN=1 `
    AZURE_DELETE_AFTER_UPLOAD=$deleteAfterUpload `
    ALLOW_OUTSIDE_SESSION=$allowOutside

Write-Host "Started ACI $ContainerName with image $image"
Write-Host "Inspect logs:"
Write-Host "  az container logs --resource-group $ResourceGroup --name $ContainerName"
Write-Host "Inspect state:"
Write-Host "  az container show --resource-group $ResourceGroup --name $ContainerName --query instanceView.state"
