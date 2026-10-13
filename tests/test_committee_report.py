import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('render', ROOT / 'skills/committee-report/scripts/render.py')
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)
NS = {'w': render.W}


def fixture(name='comparison'):
    return json.loads((ROOT / 'examples' / (name + '.json')).read_text(encoding='utf-8'))


class CommitteeReportTests(unittest.TestCase):
    def test_single_councillor_original_not_mixed(self):
        data = fixture()
        data['proposals'] = [data['proposals'][1]]
        render.validate(data)
        headers, rows = render.comparison_rows(data)
        self.assertEqual(headers, ['條文／對應關係', '現行條文', '議員提案', '說明'])
        self.assertIn('會議應於二日前公告。', rows[0][1])
        self.assertIn('甲案｜議員甲', rows[0][2])
        self.assertIn('會議應於七日前公告。', rows[0][2])
        self.assertNotIn('會議應於三日前公告。', rows[0][2])

    def test_student_and_multiple_councillors_five_columns(self):
        headers, rows = render.comparison_rows(fixture())
        self.assertEqual(len(headers), 5)
        self.assertEqual(headers[2:4], ['學生會提案', '議員提案'])
        self.assertIn('學生會案｜學生會', rows[0][2])
        self.assertIn('甲案｜議員甲', rows[0][3])
        self.assertIn('乙案｜議員乙', rows[0][3])
        self.assertIn('會議應於七日前公告。', rows[0][3])
        self.assertIn('會議應於三日前公告。', rows[0][3])
        self.assertIn('未提案（不代表照現行通過）', rows[2][2])

    def test_partial_amendment_preserves_source(self):
        data = fixture('confirmed-report')
        original = copy.deepcopy(data)
        self.assertEqual(render.resolve(data, data['rows'][1]), ('修正通過', '第八條\n報告應於七日前送交秘書處。'))
        self.assertEqual(data, original)
        data['proposals'][2]['articles'][1]['text'] = '十四日前送件，十四日後公告。'
        with self.assertRaisesRegex(ValueError, '不唯一'):
            render.resolve(data, data['rows'][1])

    def test_reserved_and_unreviewed_not_passed(self):
        data = fixture('confirmed-report')
        self.assertEqual(render.resolve(data, data['rows'][2]), ('保留送大會', '未定稿；不列為通過條文'))
        del data['rows'][6]['decision']
        self.assertEqual(render.resolve(data, data['rows'][6])[0], '尚未審查')
        data['rows'][2]['decision']['text'] = '偽造通過內容'
        with self.assertRaisesRegex(ValueError, '未決'):
            render.validate(data)

    def test_add_delete_renumber_alignment(self):
        data = fixture('confirmed-report')
        headers, rows = render.comparison_rows(data)
        self.assertIn('【刪除】', rows[3][3])
        self.assertIn('會議紀錄以紙本保存。', rows[3][1])
        self.assertIn('無現行條文', rows[4][1])
        self.assertIn('第三十條 → 第三十一條', rows[5][3])
        self.assertEqual(render.resolve(data, data['rows'][3]), ('刪除', '【刪除】'))
        self.assertEqual(render.resolve(data, data['rows'][4]), ('增訂', '第二十一條\n審查資料應公開。'))
        self.assertEqual(render.resolve(data, data['rows'][5]), ('照案通過', '第三十一條\n本規則經通過後施行。'))

    def test_pending_and_confirmation_required(self):
        data = fixture('confirmed-report')
        self.assertEqual(render.resolve(data, data['rows'][7]), ('待確認', '未定稿；不列為通過條文'))
        data['confirmation']['confirmed'] = False
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, 'unconfirmed.docx')
            with self.assertRaisesRegex(ValueError, '集中確認'):
                render.write_docx(data, path)
            self.assertFalse(path.exists())

    def test_new_whole_article_requires_user_text(self):
        data = fixture('confirmed-report')
        decision = {'status': '修正通過', 'text': '使用者提供的整條。', 'number': '第四條'}
        data['rows'][0]['decision'] = decision
        with self.assertRaisesRegex(ValueError, '使用者提供'):
            render.validate(data)
        decision['text_source'] = '使用者提供'
        self.assertEqual(render.resolve(data, data['rows'][0])[1], '第四條\n使用者提供的整條。')

    def test_docx_real_table_kai_and_long_article(self):
        data = fixture()
        long_text = '長條文測試，應自然換行且保留文字。\n' * 300
        data['rows'][0]['current']['text'] = long_text
        for font in render.FONTS:
            data['font'] = font
            with tempfile.TemporaryDirectory() as temp:
                path = render.write_docx(data, Path(temp, 'long.docx'))
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertIn('word/_rels/document.xml.rels', archive.namelist())
                    xml = ET.fromstring(archive.read('word/document.xml'))
                    styles = ET.fromstring(archive.read('word/styles.xml'))
                table = xml.find('.//w:tbl', NS)
                self.assertIsNotNone(table)
                self.assertEqual(len(table.findall('w:tr', NS)), 9)
                self.assertEqual(len(table.find('w:tr', NS).findall('w:tc', NS)), 5)
                self.assertEqual(len(xml.findall('.//w:tblHeader', NS)), 1)
                self.assertFalse(xml.findall('.//w:cantSplit', NS))
                self.assertFalse(xml.findall('.//w:trHeight', NS))
                self.assertFalse(xml.findall('.//w:drawing', NS))
                for doc in (xml, styles):
                    for node in doc.findall('.//w:rFonts', NS):
                        for attr in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                            self.assertEqual(node.get(f'{{{render.W}}}{attr}'), font)
                self.assertEqual(sum((n.text or '').count('長條文測試') for n in xml.findall('.//w:t', NS)), 300)
                with self.assertRaises(FileExistsError):
                    render.write_docx(data, path)

    def test_report_file_preserves_all_sources_and_outcomes(self):
        for has_student in (False, True):
            for font in render.FONTS:
                with self.subTest(has_student=has_student, font=font):
                    data = fixture('confirmed-report')
                    if not has_student:
                        data['proposals'] = [p for p in data['proposals'] if p['group'] != '學生會']
                    data['font'] = font
                    original = copy.deepcopy(data)
                    with tempfile.TemporaryDirectory() as temp:
                        path = render.write_docx(data, Path(temp, 'report.docx'))
                        with zipfile.ZipFile(path) as archive:
                            xml = ET.fromstring(archive.read('word/document.xml'))
                    rows = xml.findall('.//w:tbl/w:tr', NS)
                    cells = [['\n'.join(n.text or '' for n in tc.findall('.//w:t', NS)) for tc in row.findall('w:tc', NS)] for row in rows]
                    headers = ['審查會通過條文'] + (['學生會提案條文'] if has_student else []) + ['各議員提案條文', '現行條文', '說明']
                    self.assertEqual(cells[0], headers)
                    self.assertTrue(all(len(row) == len(headers) for row in cells))
                    self.assertEqual(cells[2][0], '第八條\n【修正通過】\n第八條\n報告應於七日前送交秘書處。')
                    self.assertIn('報告應於十四日前送交秘書處。', cells[2][headers.index('各議員提案條文')])
                    for row, source in zip(cells[1:], data['rows']):
                        columns = dict(zip(headers, row))
                        status = source['decision']['status']
                        self.assertIn('【' + status + '】', row[0])
                        if status in ('保留送大會', '尚未審查', '待確認'):
                            self.assertEqual(row[0], source['label'] + '\n【' + status + '】\n未定稿；不列為通過條文')
                        current = source['current']
                        self.assertEqual(columns['現行條文'], current['number'] + '\n' + current['text'] if current else '【增訂；無現行條文】')
                        self.assertIn('來源說明：' + source.get('explanation', '未提供'), columns['說明'])
                        self.assertIn('審查結論：' + status, columns['說明'])
                        self.assertIn('審查紀錄：' + source['decision']['note'], columns['說明'])
                        for proposal in data['proposals']:
                            for article in proposal['articles']:
                                if article['key'] != source['key']:
                                    continue
                                value = columns['學生會提案條文' if proposal['group'] == '學生會' else '各議員提案條文']
                                self.assertIn(proposal['id'] + '｜' + proposal['proposer'], value)
                                self.assertIn(article['number'], value)
                                self.assertIn(article['text'] if article['action'] != '刪除' else '【刪除】', value)
                                if article['action'] == '條次變更':
                                    self.assertIn(article['old_number'] + ' → ' + article['number'], value)
                    self.assertEqual(len(xml.findall('.//w:tblHeader', NS)), 1)
                    self.assertFalse(xml.findall('.//w:cantSplit', NS))
                    self.assertFalse(xml.findall('.//w:trHeight', NS))
                    widths = [int(n.get(f'{{{render.W}}}w')) for n in xml.findall('.//w:tblGrid/w:gridCol', NS)]
                    self.assertEqual(sum(widths), 14400)
                    self.assertGreater(widths[0], widths[1])
                    for node in xml.findall('.//w:rFonts', NS):
                        for attr in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                            self.assertEqual(node.get(f'{{{render.W}}}{attr}'), font)
                    self.assertEqual(data, original)

    def test_legacy_font_name_writes_actual_kai_family(self):
        data = fixture('confirmed-report')
        self.assertEqual(data['font'], '全字庫正楷體')
        with tempfile.TemporaryDirectory() as temp:
            path = render.write_docx(data, Path(temp, 'font.docx'))
            with zipfile.ZipFile(path) as archive:
                for name in ('word/document.xml', 'word/styles.xml'):
                    xml = ET.fromstring(archive.read(name))
                    for node in xml.findall('.//w:rFonts', NS):
                        for attr in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                            self.assertEqual(node.get(f'{{{render.W}}}{attr}'), '正楷體')
        # Recognize the actual family; deliberately stop at the existing-PDF guard.
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp, 'font.docx')
            source.with_suffix('.pdf').write_bytes(b'existing')
            with patch.object(render.shutil, 'which', side_effect=lambda cmd: '/fake/' + cmd), patch.object(render.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '正楷體,TW-Kai\n', '')):
                result = render.convert_pdf(source, '全字庫正楷體')
                self.assertIn('同名 PDF 已存在', result['reason'])
        # The legacy input label alone must not establish an installed family.
        with patch.object(render.shutil, 'which', side_effect=lambda cmd: '/fake/' + cmd), patch.object(render.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '全字庫正楷體\n', '')):
            result = render.convert_pdf('unused.docx', '全字庫正楷體')
            self.assertIn('未安裝正楷體', result['reason'])

    def test_pdf_missing_converter_and_font_reported(self):
        with patch.object(render.shutil, 'which', return_value=None):
            result = render.convert_pdf('unused.docx', '全字庫正楷體')
            self.assertEqual(result['status'], 'unavailable')
            self.assertIn('轉換器', result['reason'])
        with patch.object(render.shutil, 'which', side_effect=lambda cmd: '/fake/' + cmd), patch.object(render.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'Noto Sans CJK TC\n', '')):
            result = render.convert_pdf('unused.docx', '全字庫正楷體')
            self.assertEqual(result['status'], 'unavailable')
            self.assertIn('未安裝正楷體', result['reason'])

    def test_pdf_conversion_and_font_verification_paths_simulated(self):
        with tempfile.TemporaryDirectory() as temp:
            source = render.write_docx(fixture('confirmed-report'), Path(temp, 'report.docx'))
            def fake_run(args, **kwargs):
                if args[0].endswith('fc-list'):
                    return subprocess.CompletedProcess(args, 0, 'TW-Kai\n', '')
                if args[0].endswith('pdffonts'):
                    return subprocess.CompletedProcess(args, 0, 'name type encoding emb sub uni object ID\n---------------------------------------\nAAAAAA+TW-Kai CID_TrueType Identity-H yes yes yes 10 0\n', '')
                output_dir = Path(args[args.index('--outdir') + 1])
                (output_dir / 'report.pdf').write_bytes(b'%PDF-1.7\nFAKE TEST FILE')
                return subprocess.CompletedProcess(args, 0, '', '')
            with patch.object(render.shutil, 'which', side_effect=lambda cmd: '/fake/' + cmd), patch.object(render.subprocess, 'run', side_effect=fake_run):
                self.assertEqual(render.convert_pdf(source, '全字庫正楷體')['status'], 'generated')
                source.with_suffix('.pdf').unlink()
                def wrong_font(args, **kwargs):
                    if args[0].endswith('pdffonts'):
                        return subprocess.CompletedProcess(args, 0, 'header\n-----\nNotoSans CFF Identity-H yes yes yes 10 0\n', '')
                    return fake_run(args, **kwargs)
                with patch.object(render.subprocess, 'run', side_effect=wrong_font):
                    result = render.convert_pdf(source, '全字庫正楷體')
                    self.assertEqual(result['status'], 'failed')
                    self.assertFalse(source.with_suffix('.pdf').exists())

    def test_prompt_and_skill_core_identical(self):
        prompt = (ROOT / 'prompts/committee-report.md').read_text(encoding='utf-8').split('\n', 2)[2].strip()
        skill = (ROOT / 'skills/committee-report/SKILL.md').read_text(encoding='utf-8')
        core = skill.split('# committee-report\n\n', 1)[1].split('\n\n## 此儲存庫提供的檔案工具', 1)[0].strip()
        self.assertEqual(prompt, core)


if __name__ == '__main__':
    unittest.main()
