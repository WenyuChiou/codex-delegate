#!/usr/bin/env bash
# run_codex.sh — Run Codex CLI with automatic fallback to Claude on quota errors
#
# Usage:
#   ./run_codex.sh --prompt "your task here" [options]
#
# Options:
#   --prompt <text>      Task prompt (required)
#   --repo <path>        Repo working directory (default: ~/mispricing-engine)
#   --model <id>         Codex model (default: gpt-5.4)
#   --output-file <path> Codex -o output file (optional)
#   --log-file <path>    Where to write output log (default: <repo>/.ai/codex_output.txt)
#   --synchronous        Run inline, not backgrounded (default; recommended for Claude Code)
#
# Fallback chain: Codex → .fallback_claude sentinel (Claude handles it)
# Exit codes: 0 = success or fallback sentinel written, 1 = hard failure

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
PROMPT=""
REPO="${HOME}/mispricing-engine"
MODEL="gpt-5.4"
OUTPUT_FILE=""
LOG_FILE=""

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt)       PROMPT="$2";      shift 2 ;;
        --repo)         REPO="$2";        shift 2 ;;
        --model)        MODEL="$2";       shift 2 ;;
        --output-file)  OUTPUT_FILE="$2"; shift 2 ;;
        --log-file)     LOG_FILE="$2";    shift 2 ;;
        --synchronous)  shift ;;          # no-op: always synchronous
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required" >&2
    exit 1
fi

# ── Paths ─────────────────────────────────────────────────────────────────────
AI_DIR="$REPO/.ai"
LOG_PATH="${LOG_FILE:-$AI_DIR/codex_output.txt}"
DONE_PATH="$LOG_PATH.done"
ERROR_PATH="$LOG_PATH.error"
FALLBACK_PATH="$LOG_PATH.fallback_claude"

mkdir -p "$AI_DIR"

# Clean up stale sentinel files from previous runs
rm -f "$FALLBACK_PATH" "$DONE_PATH" "$ERROR_PATH"

# ── Quota / rate-limit detection ──────────────────────────────────────────────
is_quota_error() {
    local output="$1"
    local exit_code="$2"

    [[ "$exit_code" -eq 429 ]] && return 0

    local patterns=(
        "quota exceeded"
        "rate limit"
        "rate_limit"
        "quota_exceeded"
        "insufficient_quota"
        "too many requests"
        "RateLimitError"
        "exceeded your current quota"
        "429"
    )
    for p in "${patterns[@]}"; do
        if echo "$output" | grep -qi "$p"; then
            return 0
        fi
    done
    return 1
}

# ── Run Codex ─────────────────────────────────────────────────────────────────
PROMPT_FILE="$(mktemp /tmp/codex_prompt_XXXXXX.txt)"
printf '%s' "$PROMPT" > "$PROMPT_FILE"

CODEX_ARGS=("exec" "--full-auto" "-C" "$REPO" "-m" "$MODEL")
[[ -n "$OUTPUT_FILE" ]] && CODEX_ARGS+=("-o" "$OUTPUT_FILE")
CODEX_ARGS+=("$(cat "$PROMPT_FILE")")
rm -f "$PROMPT_FILE"

CODEX_BIN="${CODEX_PATH:-codex}"
OUTPUT=""
EXIT_CODE=0

# Capture both stdout and stderr
OUTPUT=$("$CODEX_BIN" "${CODEX_ARGS[@]}" 2>&1) || EXIT_CODE=$?

if is_quota_error "$OUTPUT" "$EXIT_CODE"; then
    echo "Codex quota/rate-limit exceeded — creating .fallback_claude sentinel for Claude to handle" >&2
    {
        echo "[CODEX QUOTA EXCEEDED at $(date -u +%Y-%m-%dT%H:%M:%SZ)]"
        echo "$OUTPUT"
    } > "$LOG_PATH"
    echo "ALL_QUOTA_EXCEEDED|$(date -u +%Y-%m-%dT%H:%M:%SZ)"  > "$ERROR_PATH"
    echo "FALLBACK_TO_CLAUDE|$(date -u +%Y-%m-%dT%H:%M:%SZ)"  > "$FALLBACK_PATH"
    echo "FALLBACK|$(date -u +%Y-%m-%dT%H:%M:%SZ)"            > "$DONE_PATH"
    exit 0
fi

if [[ "$EXIT_CODE" -ne 0 ]]; then
    echo "Codex hard failure (exit $EXIT_CODE)" >&2
    echo "$OUTPUT" > "$ERROR_PATH"
    exit 1
fi

# Success
{
    echo "[MODEL_USED: codex/$MODEL]"
    echo "$OUTPUT"
} > "$LOG_PATH"
echo "DONE|codex/$MODEL|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DONE_PATH"
