"""Build two self-contained TOIRA help pages from the current prototype copy."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'deployment'
FAQ_NAME = 'toira-faq.html'
GUIDE_NAME = 'toira-usage-guide.html'


def read(name):
    return (ROOT / name).read_text(encoding='utf-8-sig')


def write(name, content):
    (DEST / name).write_text(content, encoding='utf-8', newline='\n')


def build_faq(theme):
    source = read('faq.html')
    source, count = re.subn(r'<link rel="stylesheet"[^>]+>\s*', '', source)
    assert count == 2, 'FAQ stylesheet references changed'
    source, count = re.subn(r'<script src="qa\.js[^>]*>\s*</script>\s*', '', source)
    assert count == 1, 'FAQ script reference changed'
    source = source.replace(
        '<a class="qa-brand" href="index.html">TOIRA <span>作業風險評估</span>\n</a>',
        '<div class="qa-brand">TOIRA <span>作業風險評估</span></div>',
    )
    source = source.replace('href="index.html">返回評估首頁', f'href="{GUIDE_NAME}">使用說明')

    assets = sorted(set(re.findall(r'assets/qa/[^"\s<>]+\.png', source)))
    assert len(assets) == 6, 'Unexpected number of QA figures'
    for index, asset in enumerate(assets, 1):
        raw = (ROOT / asset).read_bytes()
        data = 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
        trigger_pattern = rf'<a class="qa-image-trigger" href="{re.escape(asset)}" target="_blank" rel="noopener"'
        source, count = re.subn(trigger_pattern, f'<a class="qa-image-trigger" id="qa-figure-{index}" href="#qa-figure-{index}"', source)
        assert count == 1, asset
        source, count = re.subn(rf'src="{re.escape(asset)}"', lambda match: f'src="{data}"', source)
        assert count == 1, asset

    javascript = read('qa.js')
    javascript = javascript.replace(
        "    let pictureTrigger = null;",
        """    let pictureTrigger = null;
    let originalPictureUrl = null;
    function releaseOriginalPictureUrl() {
      if (originalPictureUrl) URL.revokeObjectURL(originalPictureUrl);
      originalPictureUrl = null;
    }
    function originalPictureBlob(dataUrl) {
      const comma = dataUrl.indexOf(',');
      const bytes = Uint8Array.from(atob(dataUrl.slice(comma + 1)), character => character.charCodeAt(0));
      return new Blob([bytes], {type: 'image/png'});
    }
    window.addEventListener('pagehide', releaseOriginalPictureUrl);""",
    )
    assert "document.getElementById('qaImageOriginal').href = link.href;" in javascript
    javascript = javascript.replace(
        "        document.getElementById('qaImageOriginal').href = link.href;",
        """        const inlinePicture = link.querySelector('img').src;
        releaseOriginalPictureUrl();
        originalPictureUrl = URL.createObjectURL(originalPictureBlob(inlinePicture));
        document.getElementById('qaImageOriginal').href = originalPictureUrl;""",
    ).replace('        picture.src = link.href;', '        picture.src = inlinePicture;')
    css = theme + '\n' + read('qa.css') + '\n.qa-image-trigger:target img { max-height: none; }\n'
    source = source.replace('</head>', f'<style>\n{css}\n</style>\n</head>')
    source = source.replace('</body>', f'<script>\n{javascript}\n</script>\n</body>')
    return source


def build_guide(theme):
    cards = re.findall(r'<section class="usage-guide__card">[\s\S]*?</section>', read('usage-guide.js'))
    assert len(cards) == 4, 'Usage guide card structure changed'
    ids = ['responsibility', 'algorithm', 'limits', 'ai-data']
    labels = ['聲明與責任', '評估演算法', '使用限制', 'AI 與資料']
    cards = [card.replace('<section class="usage-guide__card">', f'<section class="usage-guide__card" id="{card_id}">').replace('<h3>', '<h2>').replace('</h3>', '</h2>') for card, card_id in zip(cards, ids)]
    navigation = '\n'.join(f'<a href="#{card_id}">{label}</a>' for card_id, label in zip(ids, labels))
    css = theme + '\n' + read('qa.css') + '''
.guide-main { max-width: 1180px; margin: auto; padding: 34px 28px 48px; }
.guide-title { margin: 0 0 24px; }
.guide-title h1 { margin: 0; color: var(--brand-900); font-size: 30px; }
.guide-title > p:last-child { margin: 10px 0 0; color: var(--ink-2); line-height: 1.8; }
.guide-nav { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 24px; }
.guide-nav a { padding: 10px 16px; border: 1px solid var(--line-strong); border-radius: var(--r-sm); background: var(--surface); color: var(--brand-800); font-size: 14px; text-decoration: none; }
.guide-nav a:hover { background: var(--brand-50); }
.guide-main .usage-guide__card { background: var(--surface); padding: 24px; scroll-margin-top: 20px; }
.guide-main .usage-guide__card h2 { margin: 0 0 14px; color: var(--brand-800); font-size: 19px; line-height: 1.5; }
.guide-main .usage-guide__card p, .guide-main .usage-guide__card li { font-size: 15px; line-height: 1.9; color: var(--ink-2); }
.guide-main .usage-guide__card li + li { margin-top: 10px; }
.guide-footer { margin-top: 28px; padding: 20px 0 0; border-top: 1px solid var(--line); }
@media (max-width: 720px) {
 .guide-main { padding: 24px 16px 36px; }
 .guide-title h1 { font-size: 27px; }
 .guide-nav { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
 .guide-nav a { text-align: center; }
 .guide-main .usage-guide__grid { grid-template-columns: minmax(0,1fr); }
 .guide-main .usage-guide__card { padding: 20px; }
 .guide-main .usage-guide__card p, .guide-main .usage-guide__card li { font-size: 14px; }
}
@media print { .guide-nav, .guide-footer, .qa-header, .qa-skip { display: none; } .guide-main { padding: 0; } .usage-guide__grid { display: block; } .usage-guide__card { margin-bottom: 12px; break-inside: avoid; } }
'''
    card_markup = '\n'.join(cards)
    return f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TOIRA 使用說明</title>
<style>
{css}
</style>
</head>
<body class="guide-page">
<a class="qa-skip" href="#guideContent">跳至使用說明內容</a>
<header class="qa-header">
<div class="qa-header-inner">
<div class="qa-brand">TOIRA <span>作業風險評估</span></div>
<a class="t-btn t-btn--outline t-btn--sm" href="{FAQ_NAME}">常見問答</a>
</div>
</header>
<main class="guide-main" id="guideContent">
<div class="guide-title">
<p class="qa-eyebrow">使用協助</p>
<h1>使用說明</h1>
<p>使用前，先了解評估方式與責任。</p>
</div>
<nav class="guide-nav" aria-label="使用說明章節">
{navigation}
</nav>
<div class="usage-guide__grid">
{card_markup}
</div>
<footer class="guide-footer">
<a class="t-btn t-btn--outline" href="{FAQ_NAME}">查閱常見問答</a>
</footer>
</main>
</body>
</html>
'''


def validate(faq, guide):
    assert faq.count('class="qa-item"') == 27
    assert faq.count('class="qa-law"') == 3
    assert len(re.findall(r'<img src="data:image/png;base64,', faq)) == 6
    assert guide.count('class="usage-guide__card"') == 4
    for page in [faq, guide]:
        assert not re.search(r'<(?:link|script)\b[^>]+(?:href|src)=', page), 'External CSS or JavaScript found'
        assert not re.search(r'<img\b[^>]*src="(?!data:)', page), 'External image found'
        page_scripts = '\n'.join(re.findall(r'<script[^>]*>([\s\S]*?)</script>', page))
        assert not re.search(r'fetch\(|XMLHttpRequest|sessionStorage|localStorage', page_scripts), 'Unexpected data access'
        assert not re.search(r'圖片來源：|內容參考：|待專家|專家逐則|仍須專家|驗證正在進行', page), 'Removed copy reintroduced'
        assert not re.search(r'href="(?:index|New|Selection)\.html', page), 'Prototype navigation dependency'
    original_laws = re.findall(r'<details class="qa-law">[\s\S]*?</details>', read('faq.html'))
    exported_laws = re.findall(r'<details class="qa-law">[\s\S]*?</details>', faq)
    assert exported_laws == original_laws, 'Law article text changed'
    original_answers = re.findall(r'<div class="qa-answer">([\s\S]*?)<div class="qa-answer-actions">', read('faq.html'))
    exported_answers = re.findall(r'<div class="qa-answer">([\s\S]*?)<div class="qa-answer-actions">', faq)
    # Image links become in-document anchors and their source is embedded;
    # compare all user-facing text independently of those HTML attributes.
    strip_markup = lambda html: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).strip()
    assert list(map(strip_markup, original_answers)) == list(map(strip_markup, exported_answers)), 'QA answer copy changed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', type=Path, dest='zip_path')
    args = parser.parse_args()
    DEST.mkdir(exist_ok=True)
    theme = read('theme.css')
    faq = build_faq(theme)
    guide = build_guide(theme)
    validate(faq, guide)
    write(FAQ_NAME, faq)
    write(GUIDE_NAME, guide)
    instructions = f'''# TOIRA 常見問答與使用說明：部署說明

## 檔案

- `{FAQ_NAME}`：27 題 QA，包含分類、關鍵字及題號搜尋、法條收合，以及 6 張圖解的放大閱讀。
- `{GUIDE_NAME}`：使用聲明、評估演算法、使用限制，以及生成式人工智慧與資料使用宣告。

兩份 HTML 均為 UTF-8，CSS、互動 JavaScript 與圖解已內嵌。無套件、後端、資料庫或外部圖片依賴，直接以現代瀏覽器開啟即可閱讀。

## 安裝

1. 將兩份 HTML 放在網站的同一個資料夾，保留檔名。
2. 以 `text/html; charset=utf-8` 提供檔案。
3. 平台的「常見問答」按鈕連到 `{FAQ_NAME}`，「使用說明」按鈕連到 `{GUIDE_NAME}`。例如放在 `/toira-help/`，則分別連到 `/toira-help/{FAQ_NAME}` 和 `/toira-help/{GUIDE_NAME}`。
4. 两頁之間使用相對連結；如改名，請同步修改兩頁的 `href`。

網站若有 Content Security Policy（CSP），需允許本頁內嵌樣式／程式，以及圖片的 `data:`、`blob:` 資源。可依單位既有政策採 CSP hash 或 nonce，無須修改網站其他頁面的政策。

## 使用特性

本交付僅提供使用協助內容，不讀取或儲存平台評估資料，不呼叫 AI 或傳送查詢問題。頁面的「查看官方法規」連結與原圖另開分頁由使用者自行點選。官方法規連結需網路；其他問答、圖解、搜尋與說明可離線使用。

圖解已內嵌於 QA，檔案約 {len(faq.encode('utf-8')) / 1024 / 1024:.1f} MiB。無需另傳 `assets/`、`theme.css` 或 `qa.js`。

## 更新內容

若修改原型的 `faq.html`、`usage-guide.js`、`qa.js`、`qa.css` 或 `theme.css`，請由開發環境重新產生交付檔：

```powershell
python scripts/build_help_pages.py
```

執行後更新本資料夾的兩份 HTML，再重新交付。此腳本不修改原型頁面或評分資料。
'''
    write('README.md', instructions.replace('两頁', '兩頁'))
    if args.zip_path:
        args.zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in [FAQ_NAME, GUIDE_NAME, 'README.md']:
                archive.write(DEST / name, arcname=name)
    print(json.dumps({
        'files': [{ 'name': name, 'bytes': (DEST / name).stat().st_size, 'sha256': hashlib.sha256((DEST / name).read_bytes()).hexdigest() } for name in [FAQ_NAME, GUIDE_NAME]],
        'qa': 27, 'images': 6, 'guideSections': 4,
        'zip': str(args.zip_path) if args.zip_path else None,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
