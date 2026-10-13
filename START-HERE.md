# committee-report 快速開始

在你使用的 AI 開一個新對話，複製下方整段啟動提示詞並送出。不需要安裝程式、懂 Git 或設定 API。

## 可複製啟動提示詞

```text
請使用一般學生看得懂的繁體中文，帶我使用 committee-report。
請讀取專案：https://github.com/Clock1025/sa-parliamentary-docs
並先實際完整讀取 skills/committee-report/SKILL.md：
https://raw.githubusercontent.com/Clock1025/sa-parliamentary-docs/develop/skills/committee-report/SKILL.md
若無法讀取或只取得部分內容，請明確告知，不得假裝已讀取；請告訴我如何貼上或上傳完整 SKILL.md，取得後先完整閱讀。
完整讀取後，再依 Skill 的規則協助會前草案對照、會中自由紀錄與會後委員會審查報告，並告訴我現在需要提供哪些資料。
審查結果由我提供，會後先集中確認再製作正式報告。DOCX／PDF 能否產生取決於你的執行環境；不能產生時請如實說明，不得宣稱檔案已完成。
```

## AI 無法讀取 GitHub 時

仍然可以提供同一份完整 Skill，不必安裝：

1. 開啟 [SKILL.md 檔案頁](https://github.com/Clock1025/sa-parliamentary-docs/blob/develop/skills/committee-report/SKILL.md)或 [Raw 全文](https://raw.githubusercontent.com/Clock1025/sa-parliamentary-docs/develop/skills/committee-report/SKILL.md)。Raw 是純文字，適合全選並複製；請包含開頭的 `---`、全部章節與最後一段，不只貼標題或摘要。
2. 把全文貼進 AI，或將完整 `SKILL.md` 下載後上傳。若平台不接受 `.md` 附件，改用貼上全文。
3. 請 AI 先完整閱讀你提供的 Skill，讀取失敗或文字截斷時明確告知，讀完後再提供會議材料。

完整 Skill 只維護在原始檔案，本頁不另存副本。若需要獨立提示詞備援，可使用 [完整可複製提示詞](prompts/committee-report.md)或 [README 的完整提示詞區塊](README.md#一鍵複製完整提示詞)。

接下來如何提供現行法規、草案與會中紀錄，請看[第一次使用說明](docs/first-time-user.md)。
