/* Local, deterministic XLSX export. No user data is sent to a backend or model. */
(() => {
    'use strict';
    const xml = value => String(value ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    const cell = (column, row, value, style = 0) => `<c r="${column}${row}" s="${style}" t="inlineStr"><is><t xml:space="preserve">${xml(value)}</t></is></c>`;
    const columns = 'ABCDEFGHIJK'.split('');
    const headers = ['1. 作業／流程名稱', '2. 辨識危害及後果', '3. 現有(已備有)防護措施', '4. 評估風險\n嚴重度', '4. 評估風險\n可能性', '4. 評估風險\n風險等級', '5. 應採取之預防設施', '6. 預估處理後之風險\n嚴重度', '6. 預估處理後之風險\n可能性', '6. 預估處理後之風險\n風險等級', '調整理由／備註'];
    const note = row => row.isManual ? [row.isRiskLowered ? `手動調降：${row.automaticRiskLevel} → ${row.initialRiskLevel}` : '使用者手動評估', `調整理由／備註：${row.manualNote || '未填寫，請補充現場判斷依據。'}`].join('\n') : '';

    window.exportToiraXlsx = async (rows, company, basis) => {
        if (!window.JSZip) throw new Error('Excel export library unavailable');
        const sheetRows = [
            `<row r="1" ht="30" customHeight="1">${cell('A', 1, 'TOIRA 風險評估表', 2)}</row>`,
            `<row r="2" ht="26" customHeight="1">${cell('A', 2, `事業單位：${company.companyName || '未填寫'}　統一編號：${company.companyUBN || '未填寫'}　行業：${company.companyIndustry || '未填寫'}`, 4)}</row>`,
            `<row r="3" ht="30" customHeight="1">${cell('A', 3, `嚴重度來源：${basis}。`, 4)}</row>`,
            `<row r="4" ht="36" customHeight="1">${cell('A', 4, '使用警示：本表為初步定性評估，應依現場實況覆核。預估處理後之風險是假設措施有效落實，並非改善驗收結果。', 4)}</row>`,
            `<row r="5" ht="48" customHeight="1">${cell('A', 5, '紅色字體代表使用者手動調整。自行調降風險者應說明現場依據並承擔調整及作業決策責任；調低分數不代表危害已降低，亦不免除法定防護義務。', 3)}</row>`,
            `<row r="6" ht="60" customHeight="1">${headers.map((value, index) => cell(columns[index], 6, value, 1)).join('')}</row>`,
        ];
        rows.forEach((item, index) => {
            const row = index + 7;
            const values = [item.processStepLabel || item.taskName, `【${item.hazardCategory}】\n${item.hazardScenario}`, (item.existingControls || []).join('\n'), item.unscored ? '—' : item.initialSeverity.replace('S', ''), item.unscored ? '—' : item.initialProbability.replace('P', ''), item.initialRiskLevel, (item.additionalControls || []).join('\n'), item.unscored ? '—' : item.residualSeverity.replace('S', ''), item.unscored ? '—' : item.residualProbability.replace('P', ''), item.residualRiskLevel, note(item)];
            sheetRows.push(`<row r="${row}">${values.map((value, col) => cell(columns[col], row, value, item.isManual && [3,4,5,7,8,9,10].includes(col) ? 3 : 0)).join('')}</row>`);
        });
        const lastRow = rows.length + 6;
        const zip = new window.JSZip();
        zip.file('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>');
        zip.file('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>');
        zip.file('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="風險評估表" sheetId="1" r:id="rId1"/></sheets></workbook>');
        zip.file('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>');
        zip.file('xl/styles.xml', `<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="4"><font><sz val="11"/><name val="Microsoft JhengHei"/><color rgb="FF1C3033"/></font><font><b/><sz val="11"/><name val="Microsoft JhengHei"/><color rgb="FFFFFFFF"/></font><font><b/><sz val="18"/><name val="Microsoft JhengHei"/><color rgb="FF0A5C5E"/></font><font><sz val="11"/><name val="Microsoft JhengHei"/><color rgb="FFC94134"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0A5C5E"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="2"><border/><border><left style="thin"><color rgb="FFC6D8D7"/></left><right style="thin"><color rgb="FFC6D8D7"/></right><top style="thin"><color rgb="FFC6D8D7"/></top><bottom style="thin"><color rgb="FFC6D8D7"/></bottom></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`);
        zip.file('xl/worksheets/sheet1.xml', `<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:K${lastRow}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="6" topLeftCell="A7" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="150"/><cols><col min="1" max="1" width="28" customWidth="1"/><col min="2" max="3" width="48" customWidth="1"/><col min="4" max="5" width="12" customWidth="1"/><col min="6" max="6" width="18" customWidth="1"/><col min="7" max="7" width="48" customWidth="1"/><col min="8" max="9" width="12" customWidth="1"/><col min="10" max="10" width="18" customWidth="1"/><col min="11" max="11" width="45" customWidth="1"/></cols><sheetData>${sheetRows.join('')}</sheetData><autoFilter ref="A6:K${lastRow}"/><mergeCells count="5">${[1,2,3,4,5].map(row => `<mergeCell ref="A${row}:K${row}"/>`).join('')}</mergeCells><pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/><pageSetup orientation="landscape" paperSize="8" fitToWidth="1" fitToHeight="0"/></worksheet>`);
        const blob = await zip.generateAsync({type:'blob', mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', compression:'DEFLATE'});
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `TOIRA_風險評估_${new Date().toISOString().slice(0,10)}.xlsx`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        return blob;
    };
})();
