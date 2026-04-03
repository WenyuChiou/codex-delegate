#!/usr/bin/env bash
# run_codex.sh — Bash wrapper for Codex CLI / Gemini CLI
#
# Handles:
#   - UTF-8 prompt encoding
#   - CJK auto-routing to Gemini CLI
#   - File-based completion signaling (log file + .done sentinel)
#   - Background-safe execution (each invocation is independent)
#
# Environment variables (configure these instead of hardcoding):
#   REPO_ROOT    — path to repo root (default: current directory)
#   CODEX_MODEL  — Codex model (default: gpt-5.4)
#   CODEX_PATH   — path to codex binary (default: codex, assumes on PATH)
#   GEMINI_PATH  — path to gemini binary (default: gemini, assumes on PATH)
#   OPENAI_API_KEY  — required for Codex
#   GEMINI_API_KEY  — required for Gemini
#
# Usage:
#   ./run_codex.sh --prompt "Read .ai/codex_task_foo.md and execute." \
#                  --repo /path/to/repo \
#                  --log-file .ai/log_foo.txt
#
#   # CJK content — auto-routes to Gemini, or force with --use-gemini
#   ./run_codex.sh --prompt "生成分析報告" --log-file .ai/log.txt
#
#   # Parallel execution (background)
#   ./run_codex.sh --prompt "Read .ai/task_a.md and execute." --log-file .ai/log_a.txt &
#   ./run_codex.sh --prompt "Read .ai/task_b.md and execute." --log-file .ai/log_b.txt &
#   wait

set -euo pipefail

# Defaults
PROMPT=""
REPO="${REPO_ROOT:-$(pwd)}"
MODEL="${CODEX_MODEL:-gpt-5.4}"
OUTPUT_FILE=""
LOG_FILE=""
USE_GEMINI=false
CODEX_BIN="${CODEX_PATH:-codex}"
GEMINI_BIN="${GEMINI_PATH:-gemini}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt|-p)       PROMPT="$2";      shift 2 ;;
        --repo|-C)         REPO="$2";        shift 2 ;;
        --model|-m)        MODEL="$2";       shift 2 ;;
        --output-file|-o)  OUTPUT_FILE="$2"; shift 2 ;;
        --log-file|-l)     LOG_FILE="$2";    shift 2 ;;
        --use-gemini)      USE_GEMINI=true;  shift   ;;
        --codex-path)      CODEX_BIN="$2";  shift 2 ;;
        --gemini-path)     GEMINI_BIN="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$PROMPT" ]]; then
    echo "Error: --prompt is required" >&2
    exit 1
fi

# Resolve log file path
AI_DIR="$REPO/.ai"
if [[ -z "$LOG_FILE" ]]; then
    LOG_FILE="$AI_DIR/codex_output.txt"
fi
DONE_FILE="$LOG_FILE.done"
ERROR_FILE="$LOG_FILE.error"

# Ensure .ai directory exists
mkdir -p "$AI_DIR"

# Auto-detect CJK characters (Unicode ranges: CJK Unified, Hiragana/Katakana, Hangul)
if [[ "$USE_GEMINI" == "false" ]]; then
    if echo "$PROMPT" | grep -qP '[\x{4e00}-\x{9fff}\x{3040}-\x{30ff}\xac00-\xd7af]' 2>/dev/null || \
       echo "$PROMPT" | python3 -c "
import sys, re
text = sys.stdin.read()
if re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
        echo "Prompt contains CJK characters — routing to Gemini CLI" >&2
        USE_GEMINI=true
    fi
fi

# Write prompt to temp file to avoid argument encoding issues
PROMPT_FILE="$(mktemp /tmp/codex_prompt_XXXXXX.txt)"
printf '%s' "$PROMPT" > "$PROMPT_FILE"
trap 'rm -f "$PROMPT_FILE"' EXIT

run_task() {
    if [[ "$USE_GEMINI" == "true" ]]; then
        SAFE_PROMPT="$(cat "$PROMPT_FILE")"
        "$GEMINI_BIN" --yolo -p "$SAFE_PROMPT" 2>&1
    else
        SAFE_PROMPT="$(cat "$PROMPT_FILE")"
        CODEX_ARGS=("exec" "--full-auto" "-C" "$REPO" "-m" "$MODEL")
        if [[ -n "$OUTPUT_FILE" ]]; then
            CODEX_ARGS+=("-o" "$OUTPUT_FILE")
        fi
        CODEX_ARGS+=("$SAFE_PROMPT")
        "$CODEX_BIN" "${CODEX_ARGS[@]}" 2>&1
    fi
}

# Execute and signal completion
if run_task > "$LOG_FILE"; then
    echo "DONE|$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DONE_FILE"
else
    EXIT_CODE=$?
    echo "Task failed with exit code $EXIT_CODE" > "$ERROR_FILE"
    echo "Error: task failed — see $ERROR_FILE" >&2
    exit $EXIT_CODE
fi
