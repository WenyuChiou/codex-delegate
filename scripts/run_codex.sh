#!/usr/bin/env bash
# run_codex.sh - Run Codex CLI with automatic fallback to Claude on quota errors.

set -euo pipefail

PYTHON_JSON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_JSON_BIN" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_JSON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_JSON_BIN="python"
    else
        echo "Error: python3 or python is required for JSON escaping" >&2
        exit 1
    fi
fi

json_escape() {
    "$PYTHON_JSON_BIN" -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

write_result_json() {
    local status="$1"
    local model="$2"
    local summary="$3"
    local timestamp
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    {
        printf '{\n'
        printf '  "status": %s,\n' "$(printf '%s' "$status" | json_escape)"
        printf '  "delegate": "codex",\n'
        printf '  "model": %s,\n' "$(printf '%s' "$model" | json_escape)"
        printf '  "log_file": %s,\n' "$(printf '%s' "$LOG_PATH" | json_escape)"
        printf '  "output_file": %s,\n' "$(printf '%s' "$OUTPUT_FILE" | json_escape)"
        printf '  "summary": %s,\n' "$(printf '%s' "$summary" | json_escape)"
        printf '  "risks": [],\n'
        printf '  "files_changed": [],\n'
        printf '  "tests_run": [],\n'
        printf '  "timestamp_utc": %s\n' "$(printf '%s' "$timestamp" | json_escape)"
        printf '}\n'
    } > "$RESULT_PATH"
}

PROMPT=""
REPO="${HOME}/mispricing-engine"
MODEL="gpt-5.4"
OUTPUT_FILE=""
LOG_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt)       PROMPT="$2";      shift 2 ;;
        --repo)         REPO="$2";        shift 2 ;;
        --model)        MODEL="$2";       shift 2 ;;
        --output-file)  OUTPUT_FILE="$2"; shift 2 ;;
        --log-file)     LOG_FILE="$2";    shift 2 ;;
        --synchronous)  shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required" >&2
    exit 1
fi

AI_DIR="$REPO/.ai"
LOG_PATH="${LOG_FILE:-$AI_DIR/codex_output.txt}"
DONE_PATH="$LOG_PATH.done"
ERROR_PATH="$LOG_PATH.error"
FALLBACK_PATH="$LOG_PATH.fallback_claude"
RESULT_PATH="$LOG_PATH.result.json"

mkdir -p "$AI_DIR"
rm -f "$FALLBACK_PATH" "$DONE_PATH" "$ERROR_PATH" "$RESULT_PATH"

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

PROMPT_FILE="$(mktemp /tmp/codex_prompt_XXXXXX.txt)"
printf '%s' "$PROMPT" > "$PROMPT_FILE"

CODEX_ARGS=("exec" "--full-auto" "-C" "$REPO" "-m" "$MODEL")
[[ -n "$OUTPUT_FILE" ]] && CODEX_ARGS+=("-o" "$OUTPUT_FILE")
CODEX_ARGS+=("$(cat "$PROMPT_FILE")")
rm -f "$PROMPT_FILE"

CODEX_BIN="${CODEX_PATH:-codex}"
OUTPUT=""
EXIT_CODE=0

OUTPUT=$("$CODEX_BIN" "${CODEX_ARGS[@]}" 2>&1) || EXIT_CODE=$?

if is_quota_error "$OUTPUT" "$EXIT_CODE"; then
    echo "Codex quota/rate-limit exceeded; creating .fallback_claude sentinel for Claude to handle" >&2
    {
        echo "[CODEX QUOTA EXCEEDED at $(date -u +%Y-%m-%dT%H:%M:%SZ)]"
        echo "$OUTPUT"
    } > "$LOG_PATH"
    echo "ALL_QUOTA_EXCEEDED|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ERROR_PATH"
    echo "FALLBACK_TO_CLAUDE|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$FALLBACK_PATH"
    echo "FALLBACK|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DONE_PATH"
    write_result_json "fallback" "codex/$MODEL" "Codex quota exceeded; Claude must take over."
    exit 0
fi

if [[ "$EXIT_CODE" -ne 0 ]]; then
    echo "Codex hard failure (exit $EXIT_CODE)" >&2
    echo "$OUTPUT" > "$ERROR_PATH"
    write_result_json "error" "codex/$MODEL" "Codex exited with a hard failure."
    exit 1
fi

{
    echo "[MODEL_USED: codex/$MODEL]"
    echo "$OUTPUT"
} > "$LOG_PATH"
echo "DONE|codex/$MODEL|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DONE_PATH"
write_result_json "success" "codex/$MODEL" "Codex completed successfully. Claude must still review diff and run verification."
