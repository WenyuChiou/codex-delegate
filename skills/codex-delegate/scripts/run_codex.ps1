param(
    [string]$Prompt = "",
    [string]$Repo = "",
    [string]$Model = "gpt-5.5",
    [string]$OutputFile = "",
    [string]$LogFile = "",
    [string]$BriefFile = "",
    [bool]$Synchronous = $true
)

# Default --repo to the caller's working directory.
# Resolved here (not at param default) so it reflects the shell's PWD
# at invocation time, not the script's parse-time location.
if (-not $Repo) { $Repo = (Get-Location).Path }

$ErrorActionPreference = "Continue"

# Brief discipline guard (parity with run_codex.sh):
# Refuse inline -Prompt > 500 chars unless an on-disk brief exists.
# Escape hatch: env var CODEX_DELEGATE_ALLOW_INLINE=1.
if ($env:CODEX_DELEGATE_ALLOW_INLINE -ne "1") {
    if ($BriefFile) {
        if (-not (Test-Path -LiteralPath $BriefFile -PathType Leaf)) {
            $alt = Join-Path $Repo $BriefFile
            if (Test-Path -LiteralPath $alt -PathType Leaf) {
                $BriefFile = $alt
            } else {
                [Console]::Error.WriteLine("codex-delegate: -BriefFile '$BriefFile' does not exist on disk.")
                [Console]::Error.WriteLine("Write the brief first; the wrapper requires it on disk for audit traceability.")
                exit 2
            }
        }
        # -C changes Codex's cwd; keep the validated brief and its derived
        # log location stable across caller-relative and repo-relative paths.
        $BriefFile = (Resolve-Path -LiteralPath $BriefFile).ProviderPath
        if (-not $Prompt) {
            $Prompt = "Read $BriefFile and execute all instructions inside."
        }
        if (-not $LogFile) {
            $briefDir = Split-Path -Parent $BriefFile
            $briefStem = [System.IO.Path]::GetFileNameWithoutExtension($BriefFile)
            $LogFile = Join-Path $briefDir "$briefStem.txt"
        }
    }
    elseif ($Prompt -and $Prompt.Length -gt 500) {
        $match = [regex]::Match($Prompt, '[^\s]*codex_task_[^\s]+\.md')
        if (-not $match.Success) {
            [Console]::Error.WriteLine("codex-delegate: brief must be on disk for audit traceability.")
            [Console]::Error.WriteLine("  Inline prompt is $($Prompt.Length) chars (> 500) and no -BriefFile passed.")
            [Console]::Error.WriteLine("  Write .ai\codex_task_<slug>.md first, then either:")
            [Console]::Error.WriteLine("    pwsh run_codex.ps1 -BriefFile .ai\codex_task_<slug>.md ...")
            [Console]::Error.WriteLine("  or")
            [Console]::Error.WriteLine("    pwsh run_codex.ps1 -Prompt 'Read .ai\codex_task_<slug>.md and execute' ...")
            [Console]::Error.WriteLine("  Escape hatch (one-off shell debugging): set CODEX_DELEGATE_ALLOW_INLINE=1")
            exit 2
        }
        $referencedBrief = $match.Value
        $checkPath = $referencedBrief
        if (-not (Test-Path -LiteralPath $checkPath -PathType Leaf)) {
            $alt = Join-Path $Repo $checkPath
            if (Test-Path -LiteralPath $alt -PathType Leaf) {
                $checkPath = $alt
            }
        }
        if (-not (Test-Path -LiteralPath $checkPath -PathType Leaf)) {
            [Console]::Error.WriteLine("codex-delegate: prompt references '$referencedBrief' but it does not exist on disk.")
            [Console]::Error.WriteLine("Write the brief first; the wrapper requires it on disk for audit traceability.")
            [Console]::Error.WriteLine("Escape hatch (one-off shell debugging): set CODEX_DELEGATE_ALLOW_INLINE=1")
            exit 2
        }
    }
}

if (-not $Prompt) {
    [Console]::Error.WriteLine("Error: -Prompt is required (or pass -BriefFile)")
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
if (Get-Command chcp -ErrorAction SilentlyContinue) { chcp 65001 | Out-Null }
# UTF-8 console, but BOM-less and set AFTER chcp: chcp re-derives the console
# encodings as BOM-emitting UTF-8, and PS 5.1 writes the InputEncoding /
# $OutputEncoding preamble into a native command's stdin pipe — codex would
# receive stray BOM bytes on its (otherwise closed) stdin.
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$logPath = if ($LogFile) { $LogFile } else { Join-Path (Join-Path $Repo ".ai") "codex_output.txt" }
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
    # A successful run is never a quota failure: without this gate, a
    # legitimate exit-0 transcript that merely mentions a quota-like
    # phrase (e.g. building a "purchase more credits" store page) would
    # be reclassified as fallback and its good diff discarded.
    if ($ExitCode -eq 0) { return $false }
    $patterns = @(
        "quota exceeded", "rate limit", "rate_limit", "quota_exceeded",
        "insufficient_quota", "too many requests", "RateLimitError",
        "exceeded your current quota", "429",
        # codex-cli 0.144.x wording (observed live 2026-07-21): keep these
        # SPECIFIC - a match turns a hard error into fallback, so a loose
        # pattern would mislabel real failures as quota and send the
        # operator waiting on a reset instead of debugging.
        "hit your usage limit", "purchase more credits"
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
        [string]$Summary,
        [string[]]$FilesChanged = @()
    )

    # Assemble JSON by hand. Windows PowerShell 5.1 `ConvertTo-Json` renders an
    # empty `@()` hashtable property as `null`, not `[]`, which would break the
    # array contract for files_changed / risks / tests_run. Each scalar is
    # escaped by running `ConvertTo-Json` on the single value. This mirrors the
    # hand-built JSON in run_codex.sh, keeping the two wrappers byte-compatible.
    function ConvertTo-JsonScalar($value) {
        if ($null -eq $value) { $value = "" }
        return ([string]$value | ConvertTo-Json -Compress)
    }

    $filesArr =
        if ($FilesChanged -and @($FilesChanged).Count -gt 0) {
            "[" + ((@($FilesChanged) | ForEach-Object { ConvertTo-JsonScalar $_ }) -join ",") + "]"
        } else { "[]" }

    $timestamp = [DateTime]::UtcNow.ToString("o")
    $json = (@(
        "{",
        ('  "status": ' + (ConvertTo-JsonScalar $Status) + ","),
        '  "delegate": "codex",',
        ('  "model": ' + (ConvertTo-JsonScalar $ModelUsed) + ","),
        ('  "log_file": ' + (ConvertTo-JsonScalar $logPath) + ","),
        ('  "output_file": ' + (ConvertTo-JsonScalar $OutputFile) + ","),
        ('  "summary": ' + (ConvertTo-JsonScalar $Summary) + ","),
        '  "risks": [],',
        ('  "files_changed": ' + $filesArr + ","),
        '  "tests_run": [],',
        ('  "timestamp_utc": ' + (ConvertTo-JsonScalar $timestamp)),
        "}"
    ) -join "`n")

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($resultPath, $json, $utf8NoBom)
}

# Snapshot the repo's changed-file set via `git status --porcelain`.
# Returns an empty array when the path is not a git work tree (or git is
# absent), so files_changed degrades to [] instead of failing the run.
function Get-GitStatusSnapshot {
    param([string]$Path)
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return @() }
    $out = & git -C $Path -c core.quotePath=false status --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) { return @() }
    # `git status` on a clean repo yields $null; strip it so the result is a
    # true empty array, not @($null) (a 1-element array holding null).
    return @($out | Where-Object { $null -ne $_ })
}

# Diff two porcelain snapshots; return the paths that became changed during
# the run. A file already dirty before the run, with an unchanged porcelain
# status line, is intentionally not re-reported (it was not this run's doing).
function Get-FilesChanged {
    param([string[]]$Before = @(), [string[]]$After = @())
    $beforeSet = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($line in $Before) { [void]$beforeSet.Add($line) }
    $paths = New-Object 'System.Collections.Generic.List[string]'
    foreach ($line in $After) {
        if ($beforeSet.Contains($line)) { continue }
        $entry = if ($line.Length -gt 3) { $line.Substring(3) } else { "" }
        if ($entry -match ' -> ') { $entry = ($entry -split ' -> ', 2)[1] }   # renamed
        $entry = $entry.Trim().Trim('"')
        if ($entry) { [void]$paths.Add($entry) }
    }
    return @($paths | Sort-Object -Unique)
}

$promptFile = Join-Path ([System.IO.Path]::GetTempPath()) "codex_prompt_$(Get-Random).txt"
$Prompt | Out-File -FilePath $promptFile -Encoding utf8
$safePrompt = Get-Content $promptFile -Raw -Encoding utf8
Remove-Item $promptFile -ErrorAction SilentlyContinue

$codexArgs = @("exec", "--sandbox", "workspace-write", "-C", $Repo, "-m", $Model)
if ($OutputFile) { $codexArgs += @("-o", $OutputFile) }
$codexArgs += $safePrompt
$codexBin = if ($env:CODEX_PATH) { $env:CODEX_PATH } else { "codex" }

# Snapshot the repo before the run so files_changed attributes edits to this
# run only. Captured before the codex call; the wrapper's own log / sentinel /
# result files are written after the after-snapshot, so they never leak in.
$changedBefore = Get-GitStatusSnapshot -Path $Repo
$filesChanged = @()

try {
    # $null pipe gives codex a closed stdin (PowerShell has no </dev/null):
    # codex exec blocks forever reading an inherited open stdin (issue #20919).
    $output = $null | & $codexBin @codexArgs 2>&1 | Out-String
    $exitCode = $LASTEXITCODE

    $changedAfter = Get-GitStatusSnapshot -Path $Repo
    $filesChanged = @(Get-FilesChanged -Before $changedBefore -After $changedAfter)

    if (Test-QuotaError -Output $output -ExitCode $exitCode) {
        Write-Warning "Codex quota/rate-limit exceeded; creating .fallback_claude sentinel for Claude to handle"
        "[CODEX QUOTA EXCEEDED at $(Get-Date -Format o)]`n$output" | Out-File $logPath -Encoding utf8
        "ALL_QUOTA_EXCEEDED|$(Get-Date -Format o)" | Out-File $errorPath -Encoding utf8
        "FALLBACK_TO_CLAUDE|$(Get-Date -Format o)" | Out-File $fallbackPath -Encoding utf8
        "FALLBACK|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
        Write-ResultJson -Status "fallback" -ModelUsed "codex/$Model" -Summary "Codex quota exceeded; Claude must take over." -FilesChanged $filesChanged
        exit 0
    }

    if ($exitCode -ne 0) {
        $output | Out-File $errorPath -Encoding utf8
        Write-ResultJson -Status "error" -ModelUsed "codex/$Model" -Summary "Codex exited with a hard failure." -FilesChanged $filesChanged
        exit 1
    }

    "[MODEL_USED: codex/$Model]`n$output" | Out-File $logPath -Encoding utf8
    "DONE|codex/$Model|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
    Write-ResultJson -Status "success" -ModelUsed "codex/$Model" -Summary "Codex completed successfully. Claude must still review diff and run verification." -FilesChanged $filesChanged
}
catch {
    $errMsg = $_.Exception.Message

    # Best-effort after-snapshot: a PowerShell-level exception may still have
    # left Codex edits on disk, so re-derive files_changed here too (the bash
    # wrapper's error path populates it for parity).
    $changedAfter = Get-GitStatusSnapshot -Path $Repo
    $filesChanged = @(Get-FilesChanged -Before $changedBefore -After $changedAfter)

    # -ExitCode 1: an exception IS a failure; the pre-gate dummy 0 would
    # now (correctly) suppress quota classification on success paths.
    if (Test-QuotaError -Output $errMsg -ExitCode 1) {
        "[CODEX QUOTA EXCEPTION at $(Get-Date -Format o)]`n$errMsg" | Out-File $logPath -Encoding utf8
        "ALL_QUOTA_EXCEEDED|$(Get-Date -Format o)" | Out-File $errorPath -Encoding utf8
        "FALLBACK_TO_CLAUDE|$(Get-Date -Format o)" | Out-File $fallbackPath -Encoding utf8
        "FALLBACK|$(Get-Date -Format o)" | Out-File $donePath -Encoding utf8
        Write-ResultJson -Status "fallback" -ModelUsed "codex/$Model" -Summary "Codex quota exception triggered fallback to Claude." -FilesChanged $filesChanged
        exit 0
    }

    $errMsg | Out-File $errorPath -Encoding utf8
    Write-ResultJson -Status "error" -ModelUsed "codex/$Model" -Summary "Codex exited with a hard failure." -FilesChanged $filesChanged
    exit 1
}
