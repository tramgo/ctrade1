param(
    [string] $SubscriptionId = "0896829f-ea22-46cd-ae31-02ab40195c2c",
    [string] $ResourceGroup = "MyRG",
    [string] $Location = "eastus2",
    [string] $EnvironmentName = "cae-ctrade1-jobs",
    [string] $AcrName = "HeldC1",
    [string] $Repository = "ctrade1/equity-12-c011ector",
    [string] $ImageTag = "shared-token",
    [string] $IdentityName = "id-ctrade1-jobs",
    [string] $StorageName = "ctrade1kitetoken",
    [string] $JobName = "kite-token-refresh",
    [string] $Cron = "0 3 * * 1-5",
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

$environmentId = "/subscriptions/${SubscriptionId}/resourceGroups/${ResourceGroup}/providers/Microsoft.App/managedEnvironments/${EnvironmentName}"
$image = "$($acr.loginServer)/${Repository}:${ImageTag}"

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
    replicaTimeout: 900
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
      - name: kite-token-refresh
        image: $image
        args:
          - refresh-token
        env:
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
          - name: KITE_ALLOW_TOTP_LOGIN
            value: "1"
          - name: COLLECTOR_CONFIG
            value: /app/zerodha_equity_collector/config/l2_collector_config.azure.json
        resources:
          cpu: 0.5
          memory: 1Gi
        volumeMounts:
          - mountPath: /kite-token
            volumeName: ctrade1-kite-token
    volumes:
      - name: ctrade1-kite-token
        storageType: AzureFile
        storageName: $StorageName
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

Write-Host "Created refresh job: $JobName cron=$Cron image=$image storage=$StorageName"
