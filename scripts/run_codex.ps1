<#
.SYNOPSIS
    Run Codex CLI or Gemini CLI with proper UTF-8 encoding and file-based completion signaling.

.DESCRIPTION
    Wrapper script for use from Cowork (or any PowerShell context where CJK encoding
    and background execution are needed). Writes output to a log file and creates a
    .done sentinel file when complete so callers can poll for completion.

    Auto-detects CJK characters in the prompt and routes to Gemini CLI automatically.

.PARAMETER Prompt
    The prompt to send to Codex or Gemini.

.PARAMETER Repo
    Path to the repository root. Defaults to $env:REPO_ROOT or current directory.

.PARAMETER Model
    Codex model to use. Defaults to $env:CODEX_MODEL or "gpt-5.4".

.PARAMETER OutputFile
    Optional: path for Codex -o flag (writes last message to this file).

.PARAMETER LogFile
    Path for the full output log. Defaults to <Repo>/.ai/codex_output.txt.
    A .done sentinel is written to <LogFile>.done on success.
    A .error sentinel is written to <LogFile>.error on failure.

.PARAMETER UseGemini
    Force routing to Gemini CLI regardless of prompt content.

.PARAMETER CodexPath
    Path to the Codex CLI executable. Defaults to $env:CODEX_PATH or "codex" (on PATH).

.PARAMETER GeminiPath
    Path to the Gemini CLI executable. Defaults to $env:GEMINI_PATH or "gemini" (on PATH).

.EXAMPLE
    # Read-only analysis (reliable from Cowork)
    $script = "path\to\run_codex.ps1"
    $repo   = $env:REPO_ROOT
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$script`" -Prompt `"Read .ai/codex_task_foo.md and analyze.`" -Repo `"$repo`" -LogFile `"$repo\.ai\log_foo.txt`"" -WindowStyle Hidden
    while (!(Test-Path "$repo\.ai\log_foo.txt.done")) { Start-Sleep 10 }
    Get-Content "$repo\.ai\log_foo.txt"

.EXAMPLE
    # CJK content auto-routes to Gemini
    .\run_codex.ps1 -Prompt "生成分析報告" -Repo $env:REPO_ROOT -LogFile ".ai\log.txt"
#>
param(
    [Parameter(Mandatory=$true)][string]$Prompt,
    [string]$Repo      = "",
    [string]$Model     = "",
    [string]$OutputFile = "",
    [string]$LogFile   = "",
    [switch]$UseGemini,
    [string]$CodexPath = "",
    [string]$GeminiPath = ""
)

$ErrorActionPreference = "Stop"

# Resolve defaults from environment variables
if (-not $Repo)       { $Repo       = if ($env:REPO_ROOT)   { $env:REPO_ROOT }   else { (Get-Location).Path } }
if (-not $Model)      { $Model      = if ($env:CODEX_MODEL) { $env:CODEX_MODEL } else { "gpt-5.4" } }
if (-not $CodexPath)  { $CodexPath  = if ($env:CODEX_PATH)  { $env:CODEX_PATH }  else { "codex" } }
if (-not $GeminiPath) { $GeminiPath = if ($env:GEMINI_PATH) { $env:GEMINI_PATH } else { "gemini" } }

# UTF-8 encoding setup — required for CJK characters in prompts and output
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING     = "utf-8"
chcp 65001 | Out-Null

# Resolve log file path
$aiDir    = Join-Path $Repo ".ai"
$logPath  = if ($LogFile) { $LogFile } else { Join-Path $aiDir "codex_output.txt" }
$donePath = "$logPath.done"
$errorPath = "$logPath.error"

# Ensure .ai directory exists
if (!(Test-Path $aiDir)) { New-Item -ItemType Directory -Path $aiDir -Force | Out-Null }

# Auto-detect CJK characters — route to Gemini if found
$hasCJK = $Prompt -match "[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"
if ($hasCJK -and -not $UseGemini) {
    Write-Warning "Prompt contains CJK characters — routing to Gemini CLI (avoids Codex encoding issues on Windows)"
    $UseGemini = $true
}

try {
    if ($UseGemini) {
        # Write prompt to temp file to avoid shell argument encoding issues with CJK
        $promptFile = "$env:TEMP\gemini_prompt_$(Get-Random).txt"
        $Prompt | Out-File -FilePath $promptFile -Encoding utf8NoBOM
        $output = & $GeminiPath --yolo -p (Get-Content $promptFile -Raw -Encoding utf8) 2>&1 | Out-String
        Remove-Item $promptFile -ErrorAction SilentlyContinue
    } else {
        # Write prompt to temp file to avoid splatting encoding issues with non-ASCII
        $promptFile = "$env:TEMP\codex_prompt_$(Get-Random).txt"
        $Prompt | Out-File -FilePath $promptFile -Encoding utf8NoBOM
        $safePrompt = Get-Content $promptFile -Raw -Encoding utf8
        Remove-Item $promptFile -ErrorAction SilentlyContinue

        $codexArgs = @("exec", "--full-auto", "-C", $Repo, "-m", $Model)
        if ($OutputFile) { $codexArgs += @("-o", $OutputFile) }
        $codexArgs += $safePrompt

        $output = & $CodexPath @codexArgs 2>&1 | Out-String
    }

    $output | Out-File -FilePath $logPath -Encoding utf8
    "DONE|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
} catch {
    $_.Exception.Message | Out-File $errorPath -Encoding utf8
    Write-Error "Task failed — see $errorPath"
    exit 1
}
