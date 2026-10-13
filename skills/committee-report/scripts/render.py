#!/usr/bin/env python3
"""Confirmed committee documents. DOCX uses only the Python standard library."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from xml.etree import ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w', W)
FONTS = ('全字庫正楷體', '標楷體')
STATUSES = ('照案通過', '修正通過', '刪除', '增訂', '保留送大會', '尚未審查', '待確認')


def element(tag, attrs=None, text=None):
    node = ET.Element(f'{{{W}}}{tag}', {f'{{{W}}}{k}': str(v) for k, v in (attrs or {}).items()})
    node.text = text
    return node


def validate(data):
    if data.get('kind') not in ('comparison', 'report'):
        raise ValueError('kind 必須是 comparison 或 report')
    if data.get('font', FONTS[0]) not in FONTS:
        raise ValueError('僅支援全字庫正楷體或標楷體，不得替換成黑體')
    if not isinstance(data.get('rows'), list) or not data['rows']:
        raise ValueError('至少需要一條條文')
    keys = [row['key'] for row in data['rows']]
    if len(keys) != len(set(keys)):
        raise ValueError('條文 key 不可重複；條次變更請使用同一穩定 key')
    ids = set()
    for proposal in data.get('proposals', []):
        if proposal['id'] in ids or proposal['group'] not in ('學生會', '議員'):
            raise ValueError('提案 id 不可重複，group 必須是學生會或議員')
        if not proposal.get('proposer'):
            raise ValueError('每案必須標示提案人')
        ids.add(proposal['id'])
        seen = set()
        for article in proposal['articles']:
            if article['key'] not in keys or article['key'] in seen:
                raise ValueError('提案條文 key 必須對應一列且不可重複')
            seen.add(article['key'])
            if article['action'] not in ('修正', '增訂', '刪除', '條次變更'):
                raise ValueError('未知提案動作')
            if article['action'] != '刪除' and not article.get('text', '').strip():
                raise ValueError('提案條文不得空白')
    for row in data['rows']:
        if not row.get('label'):
            raise ValueError('每列必須有條文辨識標籤')
        if row.get('current') is not None and not row['current'].get('text', '').strip():
            raise ValueError('現行條文不得空白；增訂用 current: null')
    if data['kind'] == 'report':
        if data.get('confirmation', {}).get('confirmed') is not True or not all(data['confirmation'].get(field) for field in ('by', 'version', 'message')):
            raise ValueError('正式報告須有使用者對本版完整結果的集中確認')
        for row in data['rows']:
            resolve(data, row)


def find_article(data, key, proposal_id):
    for proposal in data.get('proposals', []):
        if proposal['id'] == proposal_id:
            for article in proposal['articles']:
                if article['key'] == key:
                    return article
    raise ValueError(f'{key} 找不到指定提案 {proposal_id}')


def resolve(data, row):
    """Resolve an explicitly confirmed decision; never infer passage from proposals."""
    decision = row.get('decision', {'status': '尚未審查'})
    status = decision['status']
    if status not in STATUSES:
        raise ValueError('未知審查狀態')
    if status in ('保留送大會', '尚未審查', '待確認'):
        if decision.get('text') or decision.get('edits') or decision.get('proposal_id'):
            raise ValueError('未決條文不可附帶通過文字；討論內容請放 note')
        return status, '未定稿；不列為通過條文'
    if status == '刪除':
        if not row.get('current'):
            raise ValueError('刪除須對應現行條文')
        if decision.get('text') or decision.get('edits'):
            raise ValueError('刪除結果不得帶有條文文字或局部修正')
        return status, '【刪除】'
    if decision.get('text') and decision.get('edits'):
        raise ValueError('完整新文字與局部替換不可同時指定')
    if status == '照案通過':
        if decision.get('text') or decision.get('edits'):
            raise ValueError('照案通過只能引用指定案原文')
        article = find_article(data, row['key'], decision.get('proposal_id'))
        if article['action'] in ('刪除', '增訂'):
            raise ValueError('請明列刪除或增訂結果')
        return status, article['number'] + '\n' + article['text']
    if status == '增訂' and row.get('current'):
        raise ValueError('增訂須使用獨立新條文列')
    if decision.get('text'):
        if decision.get('text_source') != '使用者提供':
            raise ValueError('整條重寫須由使用者提供，不得自創條文')
        if not decision.get('number'):
            raise ValueError('完整新文字須提供條次')
        return status, decision['number'] + '\n' + decision['text']
    article = find_article(data, row['key'], decision.get('proposal_id'))
    if article['action'] == '刪除':
        raise ValueError('不可由刪除案產生通過文字')
    if status == '增訂' and article['action'] != '增訂':
        raise ValueError('增訂結果須引用增訂案')
    text = article['text']
    edits = decision.get('edits', [])
    if status == '修正通過' and not edits:
        raise ValueError('修正通過須提供明確局部修正或使用者完整文字')
    for edit in edits:
        old, new = edit['old'], edit['new']
        if not old or text.count(old) != 1:
            raise ValueError(f'局部修正「{old}」不唯一或不存在，請標示待確認')
        text = text.replace(old, new, 1)
    return status, decision.get('number', article['number']) + '\n' + text


def comparison_rows(data):
    groups = [group for group in ('學生會', '議員') if any(p['group'] == group for p in data.get('proposals', []))]
    headers = ['條文／對應關係', '現行條文'] + [g + '提案' for g in groups] + ['說明']
    result = []
    for row in data['rows']:
        current = row.get('current')
        cells = [row['label'], current['number'] + '\n' + current['text'] if current else '【增訂；無現行條文】']
        for group in groups:
            variants = []
            for proposal in data.get('proposals', []):
                if proposal['group'] != group:
                    continue
                for article in proposal['articles']:
                    if article['key'] == row['key']:
                        mapping = (article.get('old_number', current['number'] if current else '') + ' → ' + article['number']) if article['action'] == '條次變更' else article['number']
                        variants.append(f"【{proposal['id']}｜{proposal['proposer']}｜{article['action']}】\n{mapping}\n" + ('【刪除】' if article['action'] == '刪除' else article['text']))
            cells.append('\n\n'.join(variants) or '未提案（不代表照現行通過）')
        cells.append(row.get('explanation', '未提供'))
        result.append(cells)
    return headers, result


def paragraph(text, font, bold=False):
    p = element('p')
    props = element('pPr')
    props.append(element('spacing', {'after': 80, 'line': 280, 'lineRule': 'auto'}))
    p.append(props)
    for index, line in enumerate(str(text).split('\n')):
        r = element('r')
        rp = element('rPr')
        rp.append(element('rFonts', {k: font for k in ('ascii', 'hAnsi', 'eastAsia', 'cs')}))
        rp.append(element('sz', {'val': 24}))
        rp.append(element('lang', {'val': 'zh-TW', 'eastAsia': 'zh-TW'}))
        if bold:
            rp.append(element('b'))
        r.append(rp)
        if index:
            r.append(element('br'))
        t = element('t', text=line)
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        r.append(t)
        p.append(r)
    return p


def write_docx(data, destination):
    validate(data)
    font = data.get('font', FONTS[0])
    document = element('document')
    body = element('body')
    document.append(body)
    body.append(paragraph(data.get('title', '委員會審查報告' if data['kind'] == 'report' else '會前草案對照表'), font, True))
    body.append(paragraph('法規名稱：' + data.get('law', '未提供'), font))
    for field in ('committee', 'meeting', 'date'):
        if data.get(field):
            body.append(paragraph({'committee': '委員會', 'meeting': '會議', 'date': '日期'}[field] + '：' + data[field], font))
    if data['kind'] == 'report':
        body.append(paragraph('確認者：' + data['confirmation']['by'] + '；確認版：' + data['confirmation']['version'] + '\n確認紀錄：' + data['confirmation']['message'] + '\n本報告僅記載已提供並確認的結果，未決條文另列。', font))
        headers = ['條文／對應關係', '審查結果', '確認後條文', '說明／紀錄']
        rows = [[row['label'], *resolve(data, row), row.get('decision', {}).get('note', '未提供')] for row in data['rows']]
    else:
        headers, rows = comparison_rows(data)
    table = element('tbl')
    tp = element('tblPr')
    tp.append(element('tblW', {'w': 14400, 'type': 'dxa'}))
    tp.append(element('tblLayout', {'type': 'fixed'}))
    borders = element('tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        borders.append(element(edge, {'val': 'single', 'sz': 4, 'color': '808080'}))
    tp.append(borders)
    table.append(tp)
    widths = ([1500, 3000, 3900, 3900, 2100] if len(headers) == 5 else [1800, 2800, 6600, 3200] if data['kind'] == 'report' else [1800] + [int(12600 / (len(headers) - 1))] * (len(headers) - 1))
    grid = element('tblGrid')
    for width in widths:
        grid.append(element('gridCol', {'w': width}))
    table.append(grid)
    for index, cells in enumerate([headers] + rows):
        tr = element('tr')
        if index == 0:
            trpr = element('trPr')
            trpr.append(element('tblHeader'))
            tr.append(trpr)
        # No cantSplit or exact row height: long articles may flow across pages.
        for width, value in zip(widths, cells):
            tc = element('tc')
            tcpr = element('tcPr')
            tcpr.append(element('tcW', {'w': width, 'type': 'dxa'}))
            tcpr.append(element('vAlign', {'val': 'top'}))
            tc.append(tcpr)
            tc.append(paragraph(value, font, index == 0))
            tr.append(tc)
        table.append(tr)
    body.append(table)
    body.append(paragraph('文件末尾', font))
    section = element('sectPr')
    section.append(element('pgSz', {'w': 16838, 'h': 11906, 'orient': 'landscape'}))
    section.append(element('pgMar', {'top': 850, 'right': 1219, 'bottom': 850, 'left': 1219, 'header': 425, 'footer': 425, 'gutter': 0}))
    body.append(section)
    styles = element('styles')
    defaults = element('docDefaults')
    rdefault = element('rPrDefault')
    rprops = element('rPr')
    rprops.append(element('rFonts', {k: font for k in ('ascii', 'hAnsi', 'eastAsia', 'cs')}))
    rdefault.append(rprops)
    defaults.append(rdefault)
    styles.append(defaults)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create avoids overwriting a previous confirmed document.
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/_rels/document.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('word/document.xml', ET.tostring(document, encoding='utf-8', xml_declaration=True))
        archive.writestr('word/styles.xml', ET.tostring(styles, encoding='utf-8', xml_declaration=True))
    return destination


def convert_pdf(docx, font):
    """Fail closed on unavailable fonts/converter; preserve the editable DOCX."""
    if font not in FONTS:
        return {'status': 'unavailable', 'reason': '字體不符合指定楷體'}
    converter = shutil.which('soffice') or shutil.which('libreoffice')
    fontconfig = shutil.which('fc-list')
    if not converter:
        return {'status': 'unavailable', 'reason': '環境沒有 DOCX→PDF 轉換器；請在有指定楷體的 Word／LibreOffice 開啟 DOCX 後匯出 PDF'}
    if not fontconfig:
        return {'status': 'unavailable', 'reason': '無法確認指定楷體已安裝，未執行可能替換字體的轉換'}
    try:
        fonts = subprocess.run([fontconfig, '--format=%{family}\n'], capture_output=True, text=True, check=True, timeout=30).stdout
        aliases = {'全字庫正楷體': ('全字庫正楷體', 'TW-Kai', 'TW-Kai-98_1'), '標楷體': ('標楷體', 'DFKai-SB', 'BiauKai')}
        installed = {name.strip() for line in fonts.splitlines() for name in line.split(',')}
        if not installed.intersection(aliases[font]):
            return {'status': 'unavailable', 'reason': f'環境未安裝{font}；DOCX 已設定此字體，但開啟端仍須安裝，未轉換 PDF，避免無聲替換'}
        source = Path(docx).resolve()
        target = source.with_suffix('.pdf')
        if target.exists():
            return {'status': 'unavailable', 'reason': '同名 PDF 已存在，未覆寫'}
        with tempfile.TemporaryDirectory(prefix='committee-pdf-') as temp:
            profile = Path(temp, 'profile').as_uri()
            result = subprocess.run([converter, '-env:UserInstallation=' + profile, '--headless', '--convert-to', 'pdf', '--outdir', temp, str(source)], capture_output=True, text=True, timeout=120)
            generated = Path(temp, source.stem + '.pdf')
            if result.returncode != 0 or not generated.is_file() or not generated.read_bytes().startswith(b'%PDF-'):
                return {'status': 'failed', 'reason': '轉換未產生有效 PDF', 'details': (result.stdout + result.stderr)[-2000:]}
            # Installation alone is insufficient: inspect actual embedded PDF fonts.
            inspector = shutil.which('pdffonts')
            if not inspector:
                return {'status': 'unavailable', 'reason': '轉換器可用但缺少 pdffonts，無法驗證 PDF 實際使用楷體，未交付 PDF'}
            inspection = subprocess.run([inspector, str(generated)], capture_output=True, text=True, check=True, timeout=30).stdout
            font_rows = [line.split() for line in inspection.splitlines()[2:] if line.strip()]
            allowed_names = ('tw-kai', 'twkai', 'dfkai', 'biaukai', '全字庫正楷體', '標楷體')
            if not font_rows or any(not any(alias in row[0].lower() for alias in allowed_names) or len(row) < 4 or row[-5] != 'yes' for row in font_rows):
                return {'status': 'failed', 'reason': 'PDF 字體未通過楷體與內嵌檢查，未交付可能替換字體的 PDF', 'details': inspection}
            with target.open('xb') as output:
                output.write(generated.read_bytes())
        return {'status': 'generated', 'path': str(target), 'reason': '已從 DOCX 轉換並確認內嵌楷體；仍請檢視分頁與字形'}
    except (OSError, subprocess.SubprocessError) as exc:
        return {'status': 'failed', 'reason': f'PDF 轉換或驗證失敗：{exc}'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--pdf', action='store_true')
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8'))
        path = write_docx(data, args.output)
        result = {'docx': str(path), 'font': data.get('font', FONTS[0]), 'pdf': {'status': 'not_requested', 'reason': '尚未要求轉換；DOCX 字體設定不代表本機已安裝字體'}}
        if args.pdf:
            result['pdf'] = convert_pdf(path, data.get('font', FONTS[0]))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not args.pdf or result['pdf']['status'] == 'generated' else 2
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
