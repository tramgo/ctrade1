param(
    [string] $SubscriptionId = "0896829f-ea22-46cd-ae31-02ab40195c2c",
    [string] $ResourceGroup = "MyRG",
    [string] $Location = "eastus2",
    [string] $EnvironmentName = "cae-ctrade1-jobs",
    [string] $AcrName = "HeldC1",
    [string] $Repository = "ctrade1/equity-12-c011ector",
    [string] $ImageTag = "shared-token",
    [string] $IdentityName = "id-ctrade1-jobs",
    [string] $StorageAccountName = "stctrade1ramic",
    [string] $DataShareName = "ctrade1-l2-data",
    [string] $DataStorageName = "ctrade1l2data",
    [string] $TokenShareName = "ctrade1-kite-token",
    [string] $TokenStorageName = "ctrade1kitetoken",
    [string] $JobName = "equity-l2-live",
    [string] $Cron = "41 3 * * 1-5",
    [int] $ReplicaTimeoutSeconds = 25200,
    [string] $EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envPath = Join-Path $repoRoot $EnvFile

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
        if ($line -match '^\s*$' -or $line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $parts = $line -split '=', 2
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
foreach ($key in @("API_KEY", "API_SECRET", "USERNAME", "PASSWORD", "TOTP_KEY")) {
    if (-not $envValues.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envValues[$key])) {
        throw "Required .env key is missing or empty: $key"
    }
}

Invoke-Az account set --subscription $SubscriptionId

$identity = Invoke-Az identity show `
  --name $IdentityName `
  --resource-group $ResourceGroup `
  --query "{id:id}" `
  --output json | ConvertFrom-Json

$acr = Invoke-Az acr show `
  --name $AcrName `
  --query "{loginServer:loginServer}" `
  --output json | ConvertFrom-Json

$storage = Invoke-Az storage account show `
  --name $StorageAccountName `
  --resource-group $ResourceGroup `
  --query "{id:id}" `
  --output json | ConvertFrom-Json

Invoke-Az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $DataShareName `
  --quota 20 `
  --access-tier TransactionOptimized | Out-Null

Invoke-Az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccountName `
  --name $TokenShareName `
  --quota 1 `
  --access-tier TransactionOptimized | Out-Null

$storageKey = Invoke-Az storage account keys list `
  --account-name $StorageAccountName `
  --resource-group $ResourceGroup `
  --query "[0].value" `
  --output tsv

Invoke-Az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name $DataStorageName `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $DataShareName `
  --access-mode ReadWrite | Out-Null

Invoke-Az containerapp env storage set `
  --name $EnvironmentName `
  --resource-group $ResourceGroup `
  --storage-name $TokenStorageName `
  --azure-file-account-name $StorageAccountName `
  --azure-file-account-key $storageKey `
  --azure-file-share-name $TokenShareName `
  --access-mode ReadWrite | Out-Null

$environmentId = "/subscriptions/${SubscriptionId}/resourceGroups/${ResourceGroup}/providers/Microsoft.App/managedEnvironments/${EnvironmentName}"
$image = "$($acr.loginServer)/${Repository}:${ImageTag}"
$accountUrl = "https://${StorageAccountName}.blob.core.windows.net"

$yaml = @"
location: $Location
name: $JobName
identity:
  type: UserAssigned
  userAssignedIdentities:
    $($identity.id): {}
properties:
  environmentId: $environmentId
  configuration:
    triggerType: Schedule
    replicaTimeout: $ReplicaTimeoutSeconds
    replicaRetryLimit: 0
    scheduleTriggerConfig:
      cronExpression: "$Cron"
      parallelism: 1
      replicaCompletionCount: 1
    secrets:
      - name: api-key
        value: "$($envValues["API_KEY"])"
      - name: api-secret
        value: "$($envValues["API_SECRET"])"
      - name: kite-username
        value: "$($envValues["USERNAME"])"
      - name: kite-password
        value: "$($envValues["PASSWORD"])"
      - name: totp-key
        value: "$($envValues["TOTP_KEY"])"
    registries:
      - server: $($acr.loginServer)
        identity: $($identity.id)
  template:
    containers:
      - name: equity-l2-live
        image: $image
        env:
          - name: COLLECTOR_MODE
            value: l2-live
          - name: COLLECTOR_CONFIG
            value: /app/zerodha_equity_collector/config/l2_collector_config.azure.json
          - name: COLLECTOR_DATA_ROOT
            value: /data
          - name: KITE_API_KEY
            secretRef: api-key
          - name: KITE_API_SECRET
            secretRef: api-secret
          - name: KITE_USERNAME
            secretRef: kite-username
          - name: KITE_PASSWORD
            secretRef: kite-password
          - name: KITE_TOTP_KEY
            secretRef: totp-key
          - name: KITE_TOKEN_CACHE_DIR
            value: /kite-token
          - name: KITE_TOKEN_CACHE_FILE
            value: /kite-token/access_token_cache.txt
          - name: KITE_ACCESS_TOKEN_CACHE
            value: /kite-token/access_token_cache.txt
          - name: KITE_ALLOW_TOTP_LOGIN
            value: "0"
          - name: AZURE_STORAGE_ACCOUNT_URL
            value: $accountUrl
          - name: AZURE_STORAGE_CONTAINER
            value: l2-raw
          - name: AZURE_UPLOAD_AFTER_RUN
            value: "0"
        resources:
          cpu: 1
          memory: 2Gi
        volumeMounts:
          - mountPath: /data
            volumeName: ctrade1-l2-data
          - mountPath: /kite-token
            volumeName: ctrade1-kite-token
    volumes:
      - name: ctrade1-l2-data
        storageType: AzureFile
        storageName: $DataStorageName
      - name: ctrade1-kite-token
        storageType: AzureFile
        storageName: $TokenStorageName
"@

$yamlPath = Join-Path $env:TEMP "$JobName.containerapp-job.yaml"
Set-Content -Path $yamlPath -Value $yaml -Encoding UTF8
try {
    $exists = $false
    try {
        Invoke-Az containerapp job show --name $JobName --resource-group $ResourceGroup --query name --output tsv | Out-Null
        $exists = $true
    } catch {
        $exists = $false
    }
    if ($exists) {
        Invoke-Az containerapp job delete --name $JobName --resource-group $ResourceGroup --yes | Out-Null
    }
    Invoke-Az containerapp job create --name $JobName --resource-group $ResourceGroup --yaml $yamlPath | Out-Null
} finally {
    Remove-Item -LiteralPath $yamlPath -Force -ErrorAction SilentlyContinue
}

Write-Host "Created equity L2 job: $JobName cron=$Cron image=$image"
Write-Host "Data share: $DataShareName mounted at /data via $DataStorageName"
Write-Host "Token share: $TokenShareName mounted at /kite-token via $TokenStorageName"
Write-Host "Start now:"
Write-Host "  az containerapp job start --name $JobName --resource-group $ResourceGroup"
