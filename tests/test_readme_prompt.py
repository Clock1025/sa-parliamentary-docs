from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReadmePromptTests(unittest.TestCase):
    def test_embedded_prompt_matches_complete_source(self):
        readme = (ROOT / 'README.md').read_bytes()
        block = readme.split(b'<!-- committee-report-prompt:start -->', 1)[1].split(b'<!-- committee-report-prompt:end -->', 1)[0]
        match = re.search(rb'^(`{3,})text\n(.*?)^\1$', block, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2), (ROOT / 'prompts/committee-report.md').read_bytes())
        self.assertIn(b'<details>', block)
        self.assertNotIn(b'<details open', block)
