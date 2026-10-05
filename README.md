# TOIRA 原型（GitHub Pages）

平板／手機用瀏覽器開啟即可，不必安裝。

**資料庫：** 階段一寫回大眾版，另加三張十業新卡，共 169 張（`judge_draft/phase1_writeback_refined/` 為原 166 張底稿）。網頁版 `tasksLibrary.json` 只保留評估欄位（不含 MAP／hazardControlMap）。

- 作業說明：依作業名稱的字面工作描述（單一段落），不是危害導讀。
- 防護標籤：`(工程改善)` / `(工程控制)` / `(行政管理)` / `(個人防護)`。畫面三欄仍是工程改善／行政管理／個人防護；職業病的 `(工程控制)` 歸在工程改善欄，文字保留工程控制。
- 核心重點：有 `核心重點: true` 的危害組會先展開並標示；其餘預設摺疊。

行業模板用 `industryMapping.json`（與 `給璞藝/industryMapping.json` 同一份；563 列、十業 451 列；未掛上的可從「資料庫查詢」加入）。

不要用過期的 `etool2資料匯出_tasksLibrary_2.0_0811_精簡_LLM.xlsx`（四段式描述）。若需 Excel，請由 slim.llm JSON 重匯。

## 使用

1. 倉庫 Settings → Pages → Build and deployment → Source: **Deploy from a branch**
2. Branch: `main` / folder: `/ (root)`
3. 網址：https://fefe9487.github.io/TOIRA_prototype/

流程：公司資料 → 選行業模板或自選製程 → 評估（可查詢全庫、自定義製程）→ PDF。

Excel 智慧轉換需要本機後端，網頁版會改開 PDF 預覽。

## 資料快取與更新

`Selection.html` 與 `New.html` 的 JSON 讀取使用一般 HTTP 快取（`cache: 'default'`），依伺服器的有效期限重用快取，過期時由瀏覽器重新驗證。評估頁不再強制略過快取，因此從行業選擇頁進入評估頁時可重用同一份作業資料。

兩頁共用相同的 `DATA_VER` 版本值。資料檔改版且需要立即取得新版時，同步更新兩頁的 `DATA_VER`；新的版本網址會重新讀取資料。初次開啟、清除快取或強制重新整理仍可能需要下載完整資料。

目前 `DATA_VER` 是 `20261005g`。情境對照的措施只存作業庫編號，句子在 `tasksLibrary.json` 的 `AvoidItems`。給資訊廠商的欄位說明見 `改版對照_20261002.md`。
