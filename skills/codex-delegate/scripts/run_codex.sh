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

# Snapshot dirty paths and their content identity. Porcelain status alone
# misses additional edits to already-dirty files. NUL records preserve names.
# This is best-effort attribution, not a scope or acceptance gate.
git_status_snapshot() {
    "$PYTHON_JSON_BIN" -c '
import hashlib, json, os, subprocess, sys
root = sys.argv[1]
snapshot = {}
try:
    result = subprocess.run(["git", "-C", root, "status", "--porcelain=v1", "-z", "--untracked-files=all"], capture_output=True, check=True)
    records = iter(result.stdout.split(b"\0"))
    for record in records:
        if not record:
            continue
        status, relative = record[:2].decode("ascii"), os.fsdecode(record[3:])
        if "R" in status or "C" in status:
            original = os.fsdecode(next(records, b""))
            if "R" in status and original:
                snapshot[original] = [status, "renamed-source"]
        full = os.path.join(root, relative)
        try:
            if os.path.islink(full):
                identity = "link:" + os.readlink(full)
            elif os.path.isfile(full):
                digest = hashlib.sha256()
                with open(full, "rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                identity = "sha256:" + digest.hexdigest()
            else:
                identity = "directory" if os.path.isdir(full) else "missing"
        except OSError:
            identity = "unreadable"
        snapshot[relative] = [status, identity]
except (OSError, subprocess.CalledProcessError):
    pass
print(json.dumps(snapshot))
' "$1"
}

# Compare both directions: content edits, deletions, and restoring a dirty
# path to clean are changes even if Git status stays identical or disappears.
compute_files_changed_json() {
    printf "%s\n%s\n" "$1" "$2" | "$PYTHON_JSON_BIN" -c '
import json, sys
before = json.loads(sys.stdin.readline())
after = json.loads(sys.stdin.readline())
print(json.dumps(sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))))
' 2>/dev/null || printf '[]'
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
# Default --repo to the caller's working directory for portable installs.
REPO="${PWD}"
MODEL="gpt-5.5"
SANDBOX="workspace-write"
OUTPUT_FILE=""
LOG_FILE=""
BRIEF_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt)       PROMPT="$2";      shift 2 ;;
        --repo)         REPO="$2";        shift 2 ;;
        --model)        MODEL="$2";       shift 2 ;;
        --sandbox)      SANDBOX="$2";     shift 2 ;;
        --output-file)  OUTPUT_FILE="$2"; shift 2 ;;
        --log-file)     LOG_FILE="$2";    shift 2 ;;
        --brief-file)   BRIEF_FILE="$2";  shift 2 ;;
        --synchronous)  shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

case "$SANDBOX" in
    read-only|workspace-write) ;;
    *) echo "Error: --sandbox must be read-only or workspace-write" >&2; exit 2 ;;
esac

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
        # Codex -C changes its working root, not the wrapper's cwd. Resolve
        # the already-validated brief before deriving prompt and log paths;
        # otherwise a caller-relative brief can disappear (or hit a decoy)
        # after Codex changes directory. Preserve caller-first/repo fallback.
        BRIEF_FILE="$(cd -- "$(dirname -- "$BRIEF_FILE")" && pwd)/$(basename -- "$BRIEF_FILE")"
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
    # A successful run is never a quota failure: without this gate, a
    # legitimate exit-0 transcript that merely mentions a quota-like
    # phrase (e.g. building a "purchase more credits" store page) would
    # be reclassified as fallback and its good diff discarded.
    [[ "$exit_code" -eq 0 ]] && return 1

    local patterns=(
        "quota exceeded"
        "rate limit"
        "rate_limit"
        "quota_exceeded"
        "insufficient_quota"
        "too many requests"
        "RateLimitError"
        "exceeded your current quota"
        # codex-cli 0.144.x wording (observed live 2026-07-21): keep these
        # SPECIFIC - a match turns a hard error into fallback, so a loose
        # pattern would mislabel real failures as quota and send the
        # operator waiting on a reset instead of debugging.
        "hit your usage limit"
        "purchase more credits"
    )
    for p in "${patterns[@]}"; do
        if echo "$output" | grep -qi "$p"; then
            return 0
        fi
    done
    # A bare number can be a line number, port, or task content. Require an
    # HTTP/status context rather than converting unrelated failures to exit 0.
    if printf '%s' "$output" | grep -Eqi '(^|[^[:alnum:]_])(HTTP([/][0-9.]+)?[[:space:]:=-]*429|status([[:space:]_-]*code)?[[:space:]:=-]*429)([^0-9]|$)'; then
        return 0
    fi
    return 1
}

PROMPT_FILE="$(mktemp /tmp/codex_prompt_XXXXXX.txt)"
printf '%s' "$PROMPT" > "$PROMPT_FILE"

CODEX_ARGS=("exec" "--sandbox" "$SANDBOX" "-C" "$REPO" "-m" "$MODEL")
[[ -n "$OUTPUT_FILE" ]] && CODEX_ARGS+=("-o" "$OUTPUT_FILE")
CODEX_ARGS+=("$(cat "$PROMPT_FILE")")
rm -f "$PROMPT_FILE"

CODEX_BIN="${CODEX_PATH:-codex}"
OUTPUT=""
EXIT_CODE=0

# Snapshot the repo before the run so files_changed observes its path/content
# delta, including concurrent writers. Taken before the codex call; log / sentinel
# / result files are written after the after-snapshot, so they never leak in.
CHANGED_BEFORE="$(git_status_snapshot "$REPO")"

# stdin must be closed: codex exec blocks forever reading an inherited open
# stdin (upstream issue #20919; 25-min zero-byte hang on 2026-05-14).
OUTPUT=$("$CODEX_BIN" "${CODEX_ARGS[@]}" </dev/null 2>&1) || EXIT_CODE=$?

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
