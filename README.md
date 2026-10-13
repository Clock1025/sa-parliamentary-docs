# sa-parliamentary-docs

提供學生自治組織使用的 AI 議事文書生成 Skills。第一個可用工具是 **committee-report**：整理會前多案對照、接受自由會中筆記，在集中確認後製作委員會審查報告。

## 直接使用，零安裝

開啟 [完整可複製提示詞](prompts/committee-report.md)，複製全文貼進 ChatGPT 或 Claude，再貼上現行條文及草案，或直接輸入會中紀錄。不需安裝、連接 GitHub、API 金鑰或先設定學校制度。若平台支援 Skill，可使用 [SKILL.md](skills/committee-report/SKILL.md)。

例如：

> 甲案是議員甲提案，第四條是「會議應於七日前公告。」乙案是議員乙提案，第八條是「報告應於十四日前送交秘書處。」
>
> 第四條照甲案通過。第八條採乙案，十四日改七日。第十六條保留送大會。
>
> 會議結束，請整理結果讓我一次確認，再製作審查報告。

助手會保留來源、不逐條打斷會議，將保留、未審查及待確認與通過分開。若未提供第十六條原文，只能記錄保留結果並標示原文未提供，不會捏造條文。

## MVP 提供什麼

- 同法多案會前表：學生會案獨立一欄，議員多案同欄逐案標示，現行條文及說明分欄，最多五欄。
- 自由會中紀錄及七種審查狀態；明確局部修正可組合完整條文，整條新寫須由使用者提供。
- 一次集中確認後的正式報告：審查會通過條文、各議員提案條文、現行條文、說明四欄；有學生會案時加入獨立學生會提案欄，共五欄。原案全文保留，說明包含來源及審查結論；保留或結果不明不視為通過。
- 可執行的標準函式庫 DOCX 工具，真實可編輯表格、楷體設定、長條文跨頁規則；可選擇從 DOCX 轉 PDF 並回報失敗原因。

本專案不審查各校程序是否合法、不替委員會決定結果。本次未提供其他 Skill、錄音轉文字、網頁、資料庫或制度客製化。

## DOCX 與 PDF

一般使用者不需執行工具。檔案產生由具備能力的 AI 執行環境完成；純文字平台只能給可複製內容，不能宣稱已產生 DOCX／PDF。

文件指定全字庫正楷體或標楷體，DOCX 不內嵌字體；開啟端仍需具備指定字體。PDF 需要轉換器及字體，缺漏時明確告知，不能無聲換成黑體。維護者的執行方法、資料契約、退出碼及限制見 [文件產生說明](skills/committee-report/references/document-output.md)。

[會前示例](examples/comparison.json) 與 [確認後報告示例](examples/confirmed-report.json) 均為虛構驗收資料，不能冒充真實會議紀錄。

## 維護與驗收

Python 3.9 以上，可在儲存庫根目錄執行，無需第三方套件：

```sh
python3 -m unittest discover -s tests -v
```

[八項驗收案例](tests/acceptance.md) 區分工具自動測試與需在 AI 平台實測的對話行為。測試不宣稱能證明所有模型會遵守提示詞。獨立提示詞與 Skill 的共用核心以同步測試維持一致。

Git 流程：由 `main` 建立 `develop`，功能分支開 PR 至 `develop`；不直接改 `main`、不自行合併或建立 Release／Tag。

## 目錄

```text
prompts/committee-report.md        完整獨立提示詞
skills/committee-report/
  SKILL.md                        Skill 入口
  references/document-output.md   檔案契約及操作方式
  scripts/render.py               DOCX／PDF 工具
examples/                         虛構可執行範例
tests/                            自動測試與對話驗收案例
```

授權：MIT，見 [LICENSE](LICENSE)。
