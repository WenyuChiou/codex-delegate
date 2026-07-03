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

# Snapshot the repo's changed-file set via `git status --porcelain`.
# Returns empty when the path is not a git work tree (or git is absent), so
# files_changed degrades to [] instead of failing the run.
git_status_snapshot() {
    git -C "$1" -c core.quotePath=false status --porcelain 2>/dev/null || true
}

# Diff two porcelain snapshots and emit a JSON array of paths that became
# changed during the run. A file already dirty before the run, with an
# unchanged porcelain status line, is intentionally not re-reported (it was
# not this run's doing). Falls back to [] on any error.
compute_files_changed_json() {
    "$PYTHON_JSON_BIN" -c '
import json, sys
before = set(sys.argv[1].splitlines())
after = set(sys.argv[2].splitlines())
paths = set()
for line in after - before:
    entry = line[3:] if len(line) > 3 else ""
    if " -> " in entry:                 # renamed: "old -> new"
        entry = entry.split(" -> ", 1)[1]
    entry = entry.strip().strip(chr(34))
    if entry:
        paths.add(entry)
print(json.dumps(sorted(paths)))
' "$1" "$2" 2>/dev/null || printf '[]'
}

write_result_json() {
    local status="$1"
    local model="$2"
    local summary="$3"
    local files_changed_json="${4:-[]}"
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
        printf '  "files_changed": %s,\n' "$files_changed_json"
        printf '  "tests_run": [],\n'
        printf '  "timestamp_utc": %s\n' "$(printf '%s' "$timestamp" | json_escape)"
        printf '}\n'
    } > "$RESULT_PATH"
}

PROMPT=""
# Default --repo to the caller's working directory; previously hardcoded to
# the original author's mispricing-engine path, which broke fresh installs.
REPO="${PWD}"
MODEL="gpt-5.5"
OUTPUT_FILE=""
LOG_FILE=""
BRIEF_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt)       PROMPT="$2";      shift 2 ;;
        --repo)         REPO="$2";        shift 2 ;;
        --model)        MODEL="$2";       shift 2 ;;
        --output-file)  OUTPUT_FILE="$2"; shift 2 ;;
        --log-file)     LOG_FILE="$2";    shift 2 ;;
        --brief-file)   BRIEF_FILE="$2";  shift 2 ;;
        --synchronous)  shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Brief discipline: refuse inline prompts > 500 chars unless a brief is on disk.
# Auditability gap fix (research-hub v0.89.1 post-release audit, 2026-05-15):
# inline --prompt with no on-disk brief leaves orphan results and breaks
# post-hoc traceability. Escape hatch: CODEX_DELEGATE_ALLOW_INLINE=1.
if [[ "${CODEX_DELEGATE_ALLOW_INLINE:-0}" != "1" ]]; then
    if [[ -n "$BRIEF_FILE" ]]; then
        if [[ ! -f "$BRIEF_FILE" ]]; then
            if [[ -f "$REPO/$BRIEF_FILE" ]]; then
                BRIEF_FILE="$REPO/$BRIEF_FILE"
            else
                echo "codex-delegate: --brief-file '$BRIEF_FILE' does not exist on disk." >&2
                echo "Write the brief first; the wrapper requires it on disk for audit traceability." >&2
                exit 2
            fi
        fi
        if [[ -z "$PROMPT" ]]; then
            PROMPT="Read $BRIEF_FILE and execute all instructions inside."
        fi
        if [[ -z "$LOG_FILE" ]]; then
            _brief_dir=$(dirname "$BRIEF_FILE")
            _brief_stem=$(basename "$BRIEF_FILE" .md)
            LOG_FILE="$_brief_dir/$_brief_stem.txt"
        fi
    elif [[ -n "$PROMPT" && ${#PROMPT} -gt 500 ]]; then
        _referenced_brief=$(printf '%s' "$PROMPT" | grep -oE '[^[:space:]]*codex_task_[^[:space:]]+\.md' | head -1 || true)
        if [[ -z "$_referenced_brief" ]]; then
            echo "codex-delegate: brief must be on disk for audit traceability." >&2
            echo "  Inline prompt is ${#PROMPT} chars (> 500) and no --brief-file passed." >&2
            echo "  Write .ai/codex_task_<slug>.md first, then either:" >&2
            echo "    bash run_codex.sh --brief-file .ai/codex_task_<slug>.md ..." >&2
            echo "  or" >&2
            echo "    bash run_codex.sh --prompt \"Read .ai/codex_task_<slug>.md and execute\" ..." >&2
            echo "  Escape hatch (one-off shell debugging): CODEX_DELEGATE_ALLOW_INLINE=1" >&2
            exit 2
        fi
        _check_path="$_referenced_brief"
        if [[ ! -f "$_check_path" && -f "$REPO/$_check_path" ]]; then
            _check_path="$REPO/$_check_path"
        fi
        if [[ ! -f "$_check_path" ]]; then
            echo "codex-delegate: prompt references '$_referenced_brief' but it does not exist on disk." >&2
            echo "Write the brief first; the wrapper requires it on disk for audit traceability." >&2
            echo "Escape hatch (one-off shell debugging): CODEX_DELEGATE_ALLOW_INLINE=1" >&2
            exit 2
        fi
    fi
fi

if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required (or pass --brief-file)" >&2
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

CODEX_ARGS=("exec" "--sandbox" "workspace-write" "-C" "$REPO" "-m" "$MODEL")
[[ -n "$OUTPUT_FILE" ]] && CODEX_ARGS+=("-o" "$OUTPUT_FILE")
CODEX_ARGS+=("$(cat "$PROMPT_FILE")")
rm -f "$PROMPT_FILE"

CODEX_BIN="${CODEX_PATH:-codex}"
OUTPUT=""
EXIT_CODE=0

# Snapshot the repo before the run so files_changed can attribute edits to
# this run only. Taken before the codex call; the wrapper's own log / sentinel
# / result files are written after the after-snapshot, so they never leak in.
CHANGED_BEFORE="$(git_status_snapshot "$REPO")"

OUTPUT=$("$CODEX_BIN" "${CODEX_ARGS[@]}" 2>&1) || EXIT_CODE=$?

CHANGED_AFTER="$(git_status_snapshot "$REPO")"
FILES_CHANGED_JSON="$(compute_files_changed_json "$CHANGED_BEFORE" "$CHANGED_AFTER")"

if is_quota_error "$OUTPUT" "$EXIT_CODE"; then
    echo "Codex quota/rate-limit exceeded; creating .fallback_claude sentinel for Claude to handle" >&2
    {
        echo "[CODEX QUOTA EXCEEDED at $(date -u +%Y-%m-%dT%H:%M:%SZ)]"
        echo "$OUTPUT"
    } > "$LOG_PATH"
    echo "ALL_QUOTA_EXCEEDED|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$ERROR_PATH"
    echo "FALLBACK_TO_CLAUDE|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$FALLBACK_PATH"
    echo "FALLBACK|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DONE_PATH"
    write_result_json "fallback" "codex/$MODEL" "Codex quota exceeded; Claude must take over." "$FILES_CHANGED_JSON"
    exit 0
fi

if [[ "$EXIT_CODE" -ne 0 ]]; then
    echo "Codex hard failure (exit $EXIT_CODE)" >&2
    echo "$OUTPUT" > "$ERROR_PATH"
    write_result_json "error" "codex/$MODEL" "Codex exited with a hard failure." "$FILES_CHANGED_JSON"
    exit 1
fi

{
    echo "[MODEL_USED: codex/$MODEL]"
    echo "$OUTPUT"
} > "$LOG_PATH"
echo "DONE|codex/$MODEL|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DONE_PATH"
write_result_json "success" "codex/$MODEL" "Codex completed successfully. Claude must still review diff and run verification." "$FILES_CHANGED_JSON"
