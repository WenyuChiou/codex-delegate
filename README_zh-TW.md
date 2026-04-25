# Codex Delegate

> [English](README.md)

`codex-delegate` 是一個給 Claude 使用的 skill，目的是把大量、機械式、實作導向的工作交給 Codex CLI，同時把規劃、審核、驗收留在 Claude。

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

## 專案結構

```text
codex-delegate/
├── SKILL.md
├── README.md
├── README_zh-TW.md
├── scripts/
│   ├── run_codex.sh
│   └── run_codex.ps1
├── tests/
│   └── test_wrappers.py
└── references/
```

## 測試

```bash
python -m pytest -q
```

目前測試涵蓋：

- success path 的 `result.json` 輸出
- PowerShell wrapper contract 行為

## 安裝

你的環境需要先有 Codex CLI：

```bash
npm install -g @openai/codex
codex --version
```

## License

MIT
