# 本次驗證紀錄

日期：2026-10-13。範例為虛構資料，不是真實議決。

- `python3 -m unittest discover -s tests -v`：12 項測試通過。涵蓋八項核心驗收、集中確認閘門、使用者整條文字要求及提示詞／Skill 核心同步。
- CLI 實際產生 `output/comparison.docx`（9 列 × 5 欄）及 `output/report.docx`（9 列 × 4 欄）。output 是忽略的本機產物，可依範例重建，不需第三方套件。
- 當前環境另用既有 python-docx 1.2.0 讀回兩份 DOCX：表格存在、列欄數正確，報告第八條為「報告應於七日前送交秘書處。」此讀取器不是工具執行依賴。
- 實際以 `--pdf` 嘗試：環境有 LibreOffice，但未安裝全字庫正楷體，回報 `unavailable`、退出碼 2，DOCX 保留，沒有產生 PDF。
- PDF 成功與錯誤字體阻擋路徑以模擬外部工具測試，不能視為當前環境已成功轉 PDF。
- DOCX ZIP/XML 驗證含真正表格、重複表頭、楷體設定、300 行文字保留及無固定列高／禁止分列。尚未完成指定楷體下的視覺分頁驗收。
- 未呼叫 AI 模型或付費 API；實際 ChatGPT／Claude 的對話遵循度仍須依 acceptance.md 做平台驗收，不能宣稱已測過所有平台。
