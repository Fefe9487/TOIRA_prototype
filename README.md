# TOIRA 原型（GitHub Pages）

平板／手機用瀏覽器開啟即可，不必安裝。

**資料庫：** `annotation/tasksLibrary_2.0_0811.annotate.slim.llm.json`（168 筆作業）。網頁版 `tasksLibrary.json` 由此份產出，只保留評估需要的欄位（不含 MAP／hazardControlMap）。

- 作業說明：依作業名稱的字面工作描述（單一段落），不是危害導讀。
- 防護標籤：`(工程改善)` / `(行政管理)` / `(個人防護)`。畫面與報告用這三個名稱（「管理控制」顯示成「行政管理」）。
- 核心重點：有 `核心重點: true` 的危害組會先展開並標示；其餘預設摺疊。

行業模板用 `industryMapping.json`（147 筆在模板內；其餘 21 筆可從「資料庫查詢」加入）。

不要用過期的 `etool2資料匯出_tasksLibrary_2.0_0811_精簡_LLM.xlsx`（四段式描述）。若需 Excel，請由 slim.llm JSON 重匯。

## 使用

1. 倉庫 Settings → Pages → Build and deployment → Source: **Deploy from a branch**
2. Branch: `main` / folder: `/ (root)`
3. 網址：https://fefe9487.github.io/TOIRA_prototype/

流程：公司資料 → 選行業模板或自選製程 → 評估（可查詢全庫、自定義製程）→ PDF。

Excel 智慧轉換需要本機後端，網頁版會改開 PDF 預覽。
