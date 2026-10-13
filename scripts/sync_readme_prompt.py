#!/usr/bin/env python3
"""Copy the complete canonical prompt into README, or check for drift."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
START = b'<!-- committee-report-prompt:start -->'
END = b'<!-- committee-report-prompt:end -->'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check without writing files')
    args = parser.parse_args()
    source = (ROOT / 'prompts/committee-report.md').read_bytes()
    if not source.endswith(b'\n'):
        parser.error('提示詞原始檔須保留結尾換行，才能完整嵌入 Markdown 程式碼區塊')
    fence = b'`' * max(3, max((len(m.group()) for m in re.finditer(rb'`+', source)), default=0) + 1)
    path = ROOT / 'README.md'
    current = path.read_bytes()
    if current.count(START) != 1 or current.count(END) != 1:
        parser.error('README 須有且僅有一組提示詞同步標記')
    before, remainder = current.split(START, 1)
    _, after = remainder.split(END, 1)
    block = (
        START + b'\n<details>\n'
        + '<summary>展開 committee-report 完整提示詞</summary>\n\n'.encode('utf-8')
        + fence + b'text\n' + source + fence + b'\n\n</details>\n' + END
    )
    updated = before + block + after
    if args.check:
        if current != updated:
            print('README 提示詞尚未同步；請執行 python3 scripts/sync_readme_prompt.py')
            return 1
        print('README 完整提示詞與原始檔一致')
        return 0
    if current != updated:
        path.write_bytes(updated)
    print('README 完整提示詞已同步')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
