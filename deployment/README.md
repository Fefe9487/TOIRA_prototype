# TOIRA 常見問答與使用說明：部署說明

## 檔案

- `toira-faq.html`：27 題 QA，包含分類、關鍵字及題號搜尋、法條收合，以及 6 張圖解的放大閱讀。
- `toira-usage-guide.html`：使用聲明、評估演算法、使用限制，以及生成式人工智慧與資料使用宣告。

兩份 HTML 均為 UTF-8，CSS、互動 JavaScript 與圖解已內嵌。無套件、後端、資料庫或外部圖片依賴，直接以現代瀏覽器開啟即可閱讀。

## 安裝

1. 將兩份 HTML 放在網站的同一個資料夾，保留檔名。
2. 以 `text/html; charset=utf-8` 提供檔案。
3. 平台的「常見問答」按鈕連到 `toira-faq.html`，「使用說明」按鈕連到 `toira-usage-guide.html`。例如放在 `/toira-help/`，則分別連到 `/toira-help/toira-faq.html` 和 `/toira-help/toira-usage-guide.html`。
4. 兩頁之間使用相對連結；如改名，請同步修改兩頁的 `href`。

網站若有 Content Security Policy（CSP），需允許本頁內嵌樣式／程式，以及圖片的 `data:`、`blob:` 資源。可依單位既有政策採 CSP hash 或 nonce，無須修改網站其他頁面的政策。

## 使用特性

本交付僅提供使用協助內容，不讀取或儲存平台評估資料，不呼叫 AI 或傳送查詢問題。頁面的「查看官方法規」連結與原圖另開分頁由使用者自行點選。官方法規連結需網路；其他問答、圖解、搜尋與說明可離線使用。

圖解已內嵌於 QA，檔案約 11.9 MiB。無需另傳 `assets/`、`theme.css` 或 `qa.js`。

## 更新內容

若修改原型的 `faq.html`、`usage-guide.js`、`qa.js`、`qa.css` 或 `theme.css`，請由開發環境重新產生交付檔：

```powershell
python scripts/build_help_pages.py
```

執行後更新本資料夾的兩份 HTML，再重新交付。此腳本不修改原型頁面或評分資料。
