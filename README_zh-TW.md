# Codex Delegate

> [English](README.md)

`codex-delegate` 是一個給 Claude 使用的 skill，目的是把 Codex CLI 當成「implementation-heavy coding work」的執行專家，同時把規劃、審核、驗收留在 Claude。

## 定位

這個 skill 適合「很花 token，但不需要太多高階判斷」的任務，例如：

- 多檔案實作
- 機械式重構
- boilerplate 生成
- 測試骨架生成
- 大量批次修改

不適合的任務包括：

- 架構決策
- root-cause debugging
- 安全性審查
- 需求本身還不清楚的工作

## 這版更新重點

- 明確區分 Claude、Codex、Gemini 的分工
- 新增 supervisor acceptance gate
- wrapper 會輸出機器可讀的 `<log>.result.json`
- 新增 bash / PowerShell wrapper regression tests

## 核心工作流

1. Claude 先寫 task file，定義範圍與限制。
2. Claude 透過 wrapper 同步啟動 Codex。
3. Wrapper 產出 sentinel 檔與 `result.json`。
4. Claude 讀 diff、跑驗證，再決定是否接受結果。

重點是：wrapper 成功不等於任務真正驗收通過。最終判斷仍然在 Claude。

## 與 `openai/codex-plugin-cc` 的關係

OpenAI 有官方的 Codex × Claude Code 整合：
[`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc)。它是一個
功能完整、以 broker 為核心的 plugin — 跟這個 skill 是不同的設計取向。兩者
互補；下表是幫你選擇，不是排名。

| 面向 | `codex-delegate`（本 repo） | `openai/codex-plugin-cc` |
|---|---|---|
| 形式 | 單一 Claude Code skill | 多指令 plugin 套件 |
| 執行模型 | 輕量**同步** wrapper：執行 → 寫 `result.json` → 結束 | 常駐 **broker** process + 背景任務 |
| 任務追蹤 | 刻意不做 — 一次執行、一份結果 | `/codex:status`、`/codex:result`、`/codex:cancel` |
| 呼叫方式 | Claude 呼叫 skill，wrapper 腳本跑 Codex | Slash 指令（`/codex:review`、`/codex:rescue`…）加上主動式 subagent |
| 審核關卡 | Claude 自己的驗收 gate（`skills/codex-delegate/references/review-checklist.md`） | 可選的 `Stop`-hook review gate |
| 平台 | `bash` + PowerShell wrapper，Windows 實測，不需 Node | Node.js 18.18+ runtime |
| 委派路由 | Claude / Codex / Gemini 三方路由表 | 以 Codex 為主 |
| 維護者 · 授權 | Wenyu Chiou · MIT | OpenAI · Apache-2.0 |

簡單說：想要背景非同步任務、slash 指令 UX、OpenAI 官方維護的整合 → 用
`codex-plugin-cc`。想要一個輕量、同步、由 supervisor 把關、Windows 與 Linux
行為一致、並能在 Claude / Codex / Gemini 之間路由的 skill → 用
`codex-delegate`。

`codex-delegate` 也借用了官方 plugin 的東西：prompt 工程的 reference
（`skills/codex-delegate/references/codex-prompt-blocks.md`）就是改編自它的
`gpt-5-4-prompting` skill（Apache-2.0）。

## 專案結構

```text
codex-delegate/
├── .claude-plugin/plugin.json
├── README.md
├── README_zh-TW.md
├── scripts/                  # canonical wrappers for repository consumers
│   ├── run_codex.sh
│   └── run_codex.ps1
├── skills/codex-delegate/
│   ├── SKILL.md
│   ├── scripts/              # byte-identical, self-contained skill mirrors
│   └── references/
└── tests/
```

## 測試

```bash
python -m pytest -q
```

目前測試涵蓋：

- success path 的 `result.json` 輸出
- PowerShell wrapper contract 行為

## 安裝

**1. 從 [`ai-research-skills` Claude Code marketplace](https://github.com/WenyuChiou/ai-research-skills) 裝 skill：**

```bash
claude plugin marketplace add WenyuChiou/ai-research-skills
claude plugin install codex-delegate@ai-research-skills
```

Default scope 是 `user`（這個 OS 使用者帳號全域）。要只裝在當下 project
加 `--scope project`。

**2. 確認環境裡有 Codex CLI：**

```bash
npm install -g @openai/codex
codex --version
```

## License

MIT

## 執行與封裝相容性

Marketplace plugin 請從載入的 skill 使用
`bash "${CLAUDE_PLUGIN_ROOT}/scripts/run_codex.sh"`，不要假設 plugin
安裝在 `~/.claude/skills/`。直接安裝 skill 目錄時使用
`<skill-root>/scripts/run_codex.sh`；封裝內的 Bash／PowerShell wrapper
與根目錄版本必須逐位元組一致。

目前穩定 manifest 是 `0.1.0`，這個尚未發布的相容性修補提議 `0.1.1`。
版本、`-C` 工作目錄契約與未驗證項目見
[相容性紀錄](skills/codex-delegate/references/runtime-compatibility.md)。
