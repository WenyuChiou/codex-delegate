# Codex CLI 委派技能

> [English Version](README.md)

一個讓 Claude 將編程任務委派給 OpenAI Codex CLI (GPT-5.4) 的技能。Claude 負責規劃與審核，Codex 負責執行。

## 功能特色

**程式碼生成** — 透過 `codex exec --full-auto` 進行批量 Python/後端程式碼生成

**程式碼審查** — 透過 `codex exec review` 進行自動化審查

**測試生成** — 單元測試、整合測試、測試資料

**多檔案重構** — 批次編輯、常數提取、重新命名

**跨平台** — 內含 Windows cmd shell 解決方案（寫入持久化修復）

## 安裝

Codex CLI 需全域安裝：

```bash
npm install -g @openai/codex
```

驗證：`codex --version`（已測試 v0.104.0）

## 專案結構

```
codex-delegate/
├── SKILL.md              # 主要技能指令
├── README.md             # 英文文件
├── README_zh-TW.md       # 繁體中文文件
└── references/
    └── examples.md       # 完整委派範例
```

## 授權

MIT
