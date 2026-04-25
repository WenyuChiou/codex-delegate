param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [string]$Repo = "C:\Users\wenyu\mispricing-engine",
    [string]$Model = "gpt-5.4",
    [string]$OutputFile = "",
    [string]$LogFile = "",
    [bool]$Synchronous = $true
)

$ErrorActionPreference = "Stop"

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null

$logPath = if ($LogFile) { $LogFile } else { "$Repo\.ai\codex_output.txt" }
$donePath = "$logPath.done"
$errorPath = "$logPath.error"
$fallbackPath = "$logPath.fallback_claude"
$resultPath = "$logPath.result.json"

$aiDir = Join-Path $Repo ".ai"
if (!(Test-Path $aiDir)) { New-Item -ItemType Directory -Path $aiDir -Force | Out-Null }

Remove-Item $fallbackPath -ErrorAction SilentlyContinue
Remove-Item $donePath -ErrorAction SilentlyContinue
Remove-Item $errorPath -ErrorAction SilentlyContinue
Remove-Item $resultPath -ErrorAction SilentlyContinue

function Test-QuotaError {
    param([string]$Output, [int]$ExitCode)

    if ($ExitCode -eq 429) { return $true }
    $patterns = @(
        "quota exceeded", "rate limit", "rate_limit", "quota_exceeded",
        "insufficient_quota", "too many requests", "RateLimitError",
        "exceeded your current quota", "429"
    )
    foreach ($pattern in $patterns) {
        if ($Output -ilike "*$pattern*") { return $true }
    }
    return $false
}

function Write-ResultJson {
    param(
        [string]$Status,
        [string]$ModelUsed,
        [string]$Summary
    )

    $payload = [ordered]@{
        status        = $Status
        delegate      = "codex"
        model         = $ModelUsed
        log_file      = $logPath
        output_file   = $OutputFile
        summary       = $Summary
        risks         = @()
        files_changed = @()
        tests_run     = @()
        timestamp_utc = [DateTime]::UtcNow.ToString("o")
    }

    $json = $payload | ConvertTo-Json -Depth 5
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($resultPath, $json, $utf8NoBom)
}

$promptFile = "$env:TEMP\codex_prompt_$(Get-Random).txt"
$Prompt | Out-File -FilePath $promptFile -Encoding utf8
$safePrompt = Get-Content $promptFile -Raw -Encoding utf8
Remove-Item $promptFile -ErrorAction SilentlyContinue

$codexArgs = @("exec", "--full-auto", "-C", $Repo, "-m", $Model)
if ($OutputFile) { $codexArgs += @("-o", $OutputFile) }
$codexArgs += $safePrompt
$codexBin = if ($env:CODEX_PATH) { $env:CODEX_PATH } else { "codex" }

try {
    $output = & $codexBin @codexArgs 2>&1 | Out-String
    $exitCode = $LASTEXITCODE

    if (Test-QuotaError -Output $output -ExitCode $exitCode) {
        Write-Warning "Codex quota/rate-limit exceeded; creating .fallback_claude sentinel for Claude to handle"
        "[CODEX QUOTA EXCEEDED at $(Get-Date -Format o)]`n$output" | Out-File $logPath -Encoding utf8
        "ALL_QUOTA_EXCEEDED|$(Get-Date -Format o)" | Out-File $errorPath -Encoding utf8
        "FALLBACK_TO_CLAUDE|$(Get-Date -Format o)" | Out-File $fallbackPath -Encoding utf8
        "FALLBACK|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
        Write-ResultJson -Status "fallback" -ModelUsed "codex/$Model" -Summary "Codex quota exceeded; Claude must take over."
        exit 0
    }

    if ($exitCode -ne 0) {
        $output | Out-File $errorPath -Encoding utf8
        Write-ResultJson -Status "error" -ModelUsed "codex/$Model" -Summary "Codex exited with a hard failure."
        exit 1
    }

    "[MODEL_USED: codex/$Model]`n$output" | Out-File $logPath -Encoding utf8
    "DONE|codex/$Model|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
    Write-ResultJson -Status "success" -ModelUsed "codex/$Model" -Summary "Codex completed successfully. Claude must still review diff and run verification."
}
catch {
    $errMsg = $_.Exception.Message

    if (Test-QuotaError -Output $errMsg -ExitCode 0) {
        "[CODEX QUOTA EXCEPTION at $(Get-Date -Format o)]`n$errMsg" | Out-File $logPath -Encoding utf8
        "ALL_QUOTA_EXCEEDED|$(Get-Date -Format o)" | Out-File $errorPath -Encoding utf8
        "FALLBACK_TO_CLAUDE|$(Get-Date -Format o)" | Out-File $fallbackPath -Encoding utf8
        "FALLBACK|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
        Write-ResultJson -Status "fallback" -ModelUsed "codex/$Model" -Summary "Codex quota exception triggered fallback to Claude."
        exit 0
    }

    $errMsg | Out-File $errorPath -Encoding utf8
    Write-ResultJson -Status "error" -ModelUsed "codex/$Model" -Summary "Codex exited with a hard failure."
    exit 1
}
