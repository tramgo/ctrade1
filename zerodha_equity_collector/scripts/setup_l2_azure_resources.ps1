param(
    [string] $SubscriptionId = "",
    [string] $ResourceGroup = "rg-12-c011ector-shakedown-cin",
    [string] $Location = "centralindia",
    [string] $AcrName = "HeldC1",
    [string] $StorageAccountName = "st12c011ectorramic",
    [string] $BlobContainerName = "raw-12",
    [string] $FileShareName = "12-session",
    [int] $FileShareQuotaGb = 100,
    [string] $IdentityName = "id-12-c011ector",
    [string] $KeyVaultName = "kv-12-c011ector-ramic",
    [string] $LogAnalyticsName = "law-12-c011ector-cin",
    [string] $ActionGroupName = "ag-12-c011ector",
    [string] $AlertEmail = "",
    [switch] $ReuseStorageAccount
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

if (-not [string]::IsNullOrWhiteSpace($SubscriptionId)) {
    Invoke-Az account set --subscription $SubscriptionId
}

Invoke-Az group create `
  --name $ResourceGroup `
  --location $Location `
  --tags workload=12-c011ector phase=shakedown owner=expiry-2027-12-31

$storageExists = $true
$storageResourceGroup = $ResourceGroup
try {
    $storage = Invoke-Az storage account show --name $StorageAccountName | ConvertFrom-Json
    $storageResourceGroup = $storage.resourceGroup
} catch {
    $storageExists = $false
}

if ($storageExists) {
    $isDedicatedStorage = ([string]$storageResourceGroup -eq [string]$ResourceGroup)
    if (-not $ReuseStorageAccount -and -not $isDedicatedStorage) {
        throw "Storage account $StorageAccountName already exists in $storageResourceGroup. Use a new dedicated storage account name, or rerun with -ReuseStorageAccount after verifying the reuse gate."
    }
    if ($ReuseStorageAccount -or -not $isDedicatedStorage) {
        $allowedLocations = @("centralindia", "southindia")
        if ($allowedLocations -notcontains [string]$storage.location) {
            throw "Storage reuse gate failed: $StorageAccountName is in $($storage.location), expected centralindia or southindia."
        }
        if ([string]$storage.kind -ne "StorageV2") {
            throw "Storage reuse gate failed: $StorageAccountName kind is $($storage.kind), expected StorageV2."
        }
        if ($storage.networkRuleSet.defaultAction -eq "Deny") {
            throw "Storage reuse gate failed: $StorageAccountName has defaultAction=Deny, which may block ACI outbound access."
        }
        $existingPolicy = $null
        try {
            $existingPolicy = Invoke-Az storage account management-policy show `
              --account-name $StorageAccountName `
              --resource-group $storageResourceGroup | ConvertFrom-Json
        } catch {
            $existingPolicy = $null
        }
        if ($null -ne $existingPolicy -and $null -ne $existingPolicy.policy.rules -and $existingPolicy.policy.rules.Count -gt 0) {
            throw "Storage reuse gate failed: $StorageAccountName already has lifecycle rules. Use a dedicated storage account or audit the existing policy before reuse."
        }
    }
} else {
    Invoke-Az storage account create `
      --name $StorageAccountName `
      --resource-group $ResourceGroup `
      --location $Location `
      --sku Standard_LRS `
      --kind StorageV2 `
      --access-tier Cool `
      --hierarchical-namespace true `
      --min-tls-version TLS1_2 `
      --allow-blob-public-access false `
      --tags workload=12-c011ector phase=shakedown owner=expiry-2027-12-31
    $storageResourceGroup = $ResourceGroup
}

$storageId = Invoke-Az storage account show --name $StorageAccountName --resource-group $storageResourceGroup --query id -o tsv
if ([string]::IsNullOrWhiteSpace($storageId)) {
    throw "Could not resolve storage account id for $StorageAccountName in $storageResourceGroup."
}

$storageKey = Invoke-Az storage account keys list --account-name $StorageAccountName --resource-group $storageResourceGroup --query "[0].value" -o tsv
if ([string]::IsNullOrWhiteSpace($storageKey)) {
    throw "Could not read storage account key for Azure Files share creation."
}

Invoke-Az storage container create `
  --account-name $StorageAccountName `
  --account-key $storageKey `
  --name $BlobContainerName

Invoke-Az storage share-rm create `
  --resource-group $storageResourceGroup `
  --storage-account $StorageAccountName `
  --name $FileShareName `
  --quota $FileShareQuotaGb `
  --access-tier TransactionOptimized

$policy = @"
{
  "rules": [
    {
      "enabled": true,
      "name": "cool-to-cold-after-60-days",
      "type": "Lifecycle",
      "definition": {
        "filters": {
          "blobTypes": ["blockBlob"],
          "prefixMatch": [
            "$BlobContainerName/raw-12/",
            "$BlobContainerName/heartbeat/",
            "$BlobContainerName/audit/",
            "$BlobContainerName/collector_events/"
          ]
        },
        "actions": {
          "baseBlob": {
            "tierToCold": { "daysAfterModificationGreaterThan": 60 }
          }
        }
      }
    }
  ]
}
"@
$policyPath = Join-Path $env:TEMP "l2_storage_lifecycle_$StorageAccountName.json"
$policy | Set-Content -Path $policyPath -Encoding UTF8
$policyArg = "@$policyPath"
Invoke-Az storage account management-policy create `
  --account-name $StorageAccountName `
  --resource-group $storageResourceGroup `
  --policy $policyArg

try {
    Invoke-Az keyvault show --name $KeyVaultName --resource-group $ResourceGroup | Out-Null
} catch {
    Invoke-Az keyvault create `
      --name $KeyVaultName `
      --resource-group $ResourceGroup `
      --location $Location `
      --enable-rbac-authorization true `
      --retention-days 7 `
      --tags workload=12-c011ector phase=shakedown owner=expiry-2027-12-31
}

try {
    Invoke-Az identity show --name $IdentityName --resource-group $ResourceGroup | Out-Null
} catch {
    Invoke-Az identity create `
      --name $IdentityName `
      --resource-group $ResourceGroup `
      --location $Location `
      --tags workload=12-c011ector phase=shakedown owner=expiry-2027-12-31
}

$identity = Invoke-Az identity show --name $IdentityName --resource-group $ResourceGroup | ConvertFrom-Json
$principalId = $identity.principalId
$identityId = $identity.id

$acrId = Invoke-Az acr show --name $AcrName --query id -o tsv
if ([string]::IsNullOrWhiteSpace($acrId)) {
    throw "Could not resolve ACR $AcrName. Confirm the private registry exists in this subscription."
}

$kvId = Invoke-Az keyvault show --name $KeyVaultName --resource-group $ResourceGroup --query id -o tsv
$shareId = "$storageId/fileServices/default/shares/$FileShareName"

$assignments = @(
    @{ Role = "AcrPull"; Scope = $acrId },
    @{ Role = "Storage Blob Data Contributor"; Scope = "$storageId/blobServices/default/containers/$BlobContainerName" },
    @{ Role = "Storage File Data SMB Share Contributor"; Scope = $shareId },
    @{ Role = "Key Vault Secrets User"; Scope = $kvId }
)

foreach ($assignment in $assignments) {
    try {
        Invoke-Az role assignment create `
          --assignee-object-id $principalId `
          --assignee-principal-type ServicePrincipal `
          --role $assignment.Role `
          --scope $assignment.Scope | Out-Null
    } catch {
        Write-Host "Role assignment may already exist: $($assignment.Role) on $($assignment.Scope)"
    }
}

try {
    Invoke-Az monitor log-analytics workspace show --resource-group $ResourceGroup --workspace-name $LogAnalyticsName | Out-Null
} catch {
    Invoke-Az monitor log-analytics workspace create `
      --resource-group $ResourceGroup `
      --workspace-name $LogAnalyticsName `
      --location $Location `
      --retention-time 30
}

try {
    Invoke-Az monitor action-group show --resource-group $ResourceGroup --name $ActionGroupName | Out-Null
} catch {
    if ([string]::IsNullOrWhiteSpace($AlertEmail)) {
        Write-Host "Action Group $ActionGroupName not created because no email receiver was supplied."
        Write-Host "Rerun with -AlertEmail name@example.com before enabling alerts."
    } else {
        Invoke-Az monitor action-group create `
          --resource-group $ResourceGroup `
          --name $ActionGroupName `
          --short-name l2alerts `
          --action email l2-operator $AlertEmail
    }
}

Write-Host "L2 Azure resource shell is ready."
Write-Host "Resource group: $ResourceGroup"
Write-Host "Location: $Location"
Write-Host "ACR: $AcrName"
Write-Host "Storage account: $StorageAccountName"
Write-Host "Storage resource group: $storageResourceGroup"
Write-Host "Blob container: $BlobContainerName"
Write-Host "File share: $FileShareName"
Write-Host "Managed identity: $identityId"
Write-Host "Key Vault: $KeyVaultName"
Write-Host "Populate Key Vault secrets before manual ACI run:"
Write-Host "  kite-api-key, kite-api-secret, kite-username, kite-password, kite-totp-key, optional access-token"
