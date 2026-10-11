/* TOIRA 共用使用說明；同一分頁讀過本版後，可由頂端隨時重新開啟。 */
(() => {
    const VERSION = '20261011d';
    const STORAGE_KEY = 'toira.usageGuide.read';
    const markup = `<dialog class="usage-guide" id="usage-guide" aria-labelledby="usage-guide-title">
        <div class="usage-guide__header">
            <div>
                <h2 id="usage-guide-title">使用前，先了解評估方式與責任</h2>
                <p>TOIRA 使用說明｜聲明、演算法、使用限制與資料安全</p>
            </div>
            <button class="t-btn t-btn--ghost" onclick="closeUsageGuide()" aria-label="關閉使用說明">✕</button>
        </div>
        <div class="usage-guide__body">
            <div class="usage-guide__grid">
                <section class="usage-guide__card">
                    <h3>1. 聲明與使用者責任</h3>
                    <ul>
                        <li>本工具協助作業現場初步危害辨識與改善設施建議，<strong>不保證符合現場狀況</strong>，使用者應自行評估。</li>
                        <li>改善設施勾選代表現場已備有並落實；尚未執行的改善設施，不應勾為已完成。</li>
                        <li>依職業安全衛生管理辦法第 12 條之 1，雇主應實施風險評估並採取必要預防設備及措施；此義務不因勾選防護措施或自行調低風險等級而免除。</li>
                    </ul>
                </section>
                <section class="usage-guide__card">
                    <h3>2. 演算法如何產生風險等級？</h3>
                    <ul>
                        <li>原型保留嚴重度開關：關閉採生成時估算；開啟採 110–114 年（5 年）職災統計與分級規則，公版參考等級為 S2–S5。立即危險類型採 S5；職業病可恢復採 S4、不可恢復採 S5。</li>
                        <li>可能性 P 依核心、工程及管理措施的落實狀態分級，無情境對照時依措施勾選比例推算。</li>
                        <li>以固定 <strong>5×5 S／P 矩陣</strong>查得風險等級，非 AI 即時判斷或實測事故機率。</li>
                        <li>「預估處理後之風險」假設措施落實且有效，<strong>不是改善驗收結果</strong>。</li>
                    </ul>
                </section>
                <section class="usage-guide__card">
                    <h3>3. 使用限制</h3>
                    <ul>
                        <li>TOIRA 提供的作業資料不一定能涵蓋所有現場條件，核心危害也不等於完整危害清單，應由具相關能力的人員覆核。</li>
                        <li>一定規模、特殊危害及複雜製程，應依法採用更完整的評估、監測與管理方法。</li>
                        <li>如有立即發生危險之虞，應先停止相關作業並退避，<strong>不得等待評分或改善期限</strong>。</li>
                    </ul>
                </section>
                <section class="usage-guide__card">
                    <h3>4. 生成式人工智慧使用宣告</h3>
                    <p>本平台於作業資料建置階段，使用生成式人工智慧輔助撰寫。作業資料須經專家審查後，才提供正式查詢與評估使用。</p>
                    <p>使用者填寫的資料與評估作業，保留供<strong>匿名化之描述性分析</strong>使用；<strong>不提供人工智慧讀取，也不用於人工智慧再次訓練</strong>。</p>
                </section>
            </div>
        </div>
        <div class="usage-guide__footer">
            <span>可隨時由頁面頂端「使用說明」重新開啟。<br><a href="faq.html" target="_blank" rel="noopener">查閱常見問答（另開分頁）</a></span>
            <button class="t-btn t-btn--primary" id="usage-guide-continue" onclick="closeUsageGuide()">知道了，開始評估</button>
        </div>
    </dialog>`;
    let returnFocus = null;

    function openUsageGuide() {
        const guide = document.getElementById('usage-guide');
        if (!guide || guide.open) return;
        returnFocus = document.activeElement;
        guide.showModal();
    }

    function closeUsageGuide() {
        document.getElementById('usage-guide')?.close();
    }

    window.openUsageGuide = openUsageGuide;
    window.closeUsageGuide = closeUsageGuide;

    function initialize() {
        document.body.insertAdjacentHTML('beforeend', markup);
        const guide = document.getElementById('usage-guide');
        let trigger = document.getElementById('usage-guide-open');
        if (!trigger) {
            const header = document.querySelector('.t-app-bar__tools') || document.querySelector('header');
            if (header) {
                trigger = document.createElement('button');
                trigger.type = 'button';
                trigger.id = 'usage-guide-open';
                trigger.className = 't-btn t-btn--outline t-btn--sm';
                if (header.closest('.t-app-bar')) trigger.classList.add('usage-guide-trigger');
                trigger.textContent = '使用說明';
                trigger.addEventListener('click', openUsageGuide);
                header.appendChild(trigger);
            }
        }
        if (trigger) {
            trigger.setAttribute('aria-haspopup', 'dialog');
            trigger.setAttribute('aria-controls', 'usage-guide');
        }
        const tools = document.querySelector('.t-app-bar__tools') || document.querySelector('header');
        if (tools && !document.getElementById('qa-open')) {
            const link = document.createElement('a');
            link.id = 'qa-open';
            link.className = 't-btn t-btn--outline t-btn--sm' + (tools.closest('.t-app-bar') ? ' usage-guide-trigger' : '');
            link.href = 'faq.html';
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = '常見問答';
            link.setAttribute('aria-label', '常見問答（另開分頁）');
            tools.appendChild(link);
        }
        guide.addEventListener('close', () => {
            try { sessionStorage.setItem(STORAGE_KEY, VERSION); } catch (err) { /* 儲存受限仍可閱讀 */ }
            if (returnFocus && returnFocus !== document.body && returnFocus.isConnected) returnFocus.focus();
        });
        let read = false;
        try { read = sessionStorage.getItem(STORAGE_KEY) === VERSION; } catch (err) { /* 儲存受限仍顯示 */ }
        if (!read) openUsageGuide();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
    else initialize();
})();
