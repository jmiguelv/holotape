"""Offline regressions for legacy Notion exports. No network or credentials."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import notion_markdown as md


class MarkdownTests(unittest.TestCase):
    def test_warning_icon_is_not_duplicated_in_body(self):
        b = md.render('<aside>\n🚨\n\nCheck order.\n</aside>')[0]
        self.assertEqual(b['callout']['icon'], {'type': 'emoji', 'emoji': '🚨'})
        self.assertEqual(b['callout']['color'], 'yellow_background')
        self.assertEqual(''.join(x['text']['content'] for x in b['callout']['rich_text']), 'Check order.')

    def test_source_question_icon_is_retained(self):
        url = 'https://app.notion.com/icons/question-mark_gray.svg'
        b = md.render('<aside>\n<img\n src="' + url + '" />\n\nWhy?\n</aside>')[0]
        self.assertEqual(b['callout']['icon'], {'type': 'external', 'external': {'url': url}})

    def test_callout_rejects_non_notion_fetch_targets(self):
        with self.assertRaises(ValueError):
            md.render('<aside>\n<img src="https://127.0.0.1/private" />\nNote\n</aside>')

    def test_strikethrough_and_inline_code(self):
        rich = md.rich('Use ~~old~~ `new`.')
        self.assertTrue(any(x.get('annotations', {}).get('strikethrough') for x in rich))
        self.assertTrue(any(x.get('annotations', {}).get('code') for x in rich))

    def test_mermaid_and_numbered_workflow(self):
        nodes = md.render('1. Select data.\n    - Record lineage.\n2. Review.\n\n```mermaid\nflowchart LR\nA-->B\n```')
        self.assertEqual(nodes[0]['type'], 'numbered_list_item')
        self.assertEqual(nodes[0]['numbered_list_item']['children'][0]['type'], 'bulleted_list_item')
        self.assertEqual(nodes[-1]['code']['language'], 'mermaid')

    def test_star_bullets_are_not_consumed_as_italic_prose(self):
        nodes = md.render('Match the labels:\n* First region\n* Second region')
        self.assertEqual([b['type'] for b in nodes], ['paragraph', 'bulleted_list_item', 'bulleted_list_item'])

    def test_multiline_table_cells(self):
        b = md.render('| A | B |\n| --- | --- |\n| one,\ntwo | first\n\nsecond |')[0]
        row = b['table']['children'][1]['table_row']['cells']
        self.assertIn('two', ''.join(x['text']['content'] for x in row[0]))
        self.assertIn('second', ''.join(x['text']['content'] for x in row[1]))

    def test_api_can_coalesce_rich_text_and_normalise_root_urls(self):
        self.assertEqual(md.rich_signature(md.text('x' * 5000)), md.rich_signature([{'type': 'text', 'text': {'content': 'x' * 5000}}]))
        self.assertEqual(md.rich_signature(md.rich('[a](https://example.com)')), md.rich_signature(md.rich('[a](https://example.com/)')))

    def test_python_source_is_data_not_executed(self):
        b = md.render('```python\nraise RuntimeError("do not execute")\n```')[0]
        self.assertEqual(b['type'], 'code')
        self.assertEqual(b['code']['language'], 'python')


class ExportTests(unittest.TestCase):
    def test_only_explicit_checkboxes_become_actions_and_nesting_survives(self):
        source = '# Example\n\nStatus: In progress\n\n- [ ] Parent\n    - [x] Child\n- Completed\n    - [x] Other\n\n8 October 2026\n\nMaybe benchmark again.\n```text\n- [ ] Not an action\n```\n'
        doc = md.prepare_export(source)
        self.assertEqual(len(doc['actions']), 3)
        self.assertEqual([a['parent'] for a in doc['actions']], [None, 0, None])
        self.assertIn('Maybe benchmark again.', doc['log'])
        self.assertIn('- [ ] Not an action', doc['log'])

    def test_placeholder_is_not_an_action(self):
        doc = md.prepare_export('# Example\n\n- [ ] *@who, [what](, by [date])*\n- [ ] Real action')
        self.assertEqual(len(doc['actions']), 1)

    def test_relative_today_is_not_backdated_or_inferred(self):
        doc = md.prepare_export('# Example\n\n- [ ] Upload by today at 2pm\n- [ ] Review by 8 October 2026\n\n@Today\n\nInstalled search.')
        self.assertIsNone(doc['actions'][0]['due'])
        self.assertEqual(doc['actions'][1]['due'], '2026-10-08')
        self.assertIn('Undated source update (@Today)', doc['log'])
        self.assertNotIn('<mention-date', doc['log'])

    def test_credentials_are_omitted_without_echoing_values(self):
        marker = 'EXAMPLE_ONLY_DO_NOT_COPY'
        source = '# Example\n\n21 October 2026\n\nUseful note.\npassword: ' + marker + '\nFiles: https://www.dropbox.com/sm/password?rlkey=' + marker
        doc = md.prepare_export(source)
        self.assertNotIn(marker, str(doc))
        self.assertIn('Useful note.', doc['log'])
        self.assertEqual(len(doc['warnings']), 2)

    def test_no_source_body_does_not_invent_a_work_log(self):
        doc = md.prepare_export('# Example\n\nPerson: Researcher\nStatus: Not started')
        self.assertFalse(doc['log'].strip())
        self.assertFalse(doc['context'].strip())
        self.assertEqual(doc['actions'], [])

    def test_export_dates_are_normalised_but_not_undated_prose(self):
        doc = md.prepare_export('# Example\n\n<u>3 August 2026</u>\n\nProgress.\n\n## 8 October 2026\n\nMore progress.')
        self.assertIn('## 3 August 2026', doc['log'])
        self.assertIn('## 8 October 2026', doc['log'])


class MediaTests(unittest.TestCase):
    def test_assets_cannot_escape_the_export_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'export'
            root.mkdir()
            source = root / 'Example.md'
            source.write_text('# Example')
            outside = Path(directory) / 'outside.txt'
            outside.write_text('metadata')
            for reference in ('../outside.txt', '%2e%2e/outside.txt', str(outside)):
                with self.assertRaises(ValueError):
                    md.safe_asset(source, reference)
            (root / 'link.txt').symlink_to(outside)
            with self.assertRaises(ValueError):
                md.safe_asset(source, 'link.txt')

    def test_local_text_attachment_is_a_file_not_a_broken_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'Example.md'
            source.write_text('# Example')
            (root / 'list.txt').write_text('page-001.png\n')
            b = md.render('[list.txt](list.txt)', source_file=source)[0]
            self.assertEqual(b['type'], 'file')
            self.assertEqual(b['file']['_asset'], 'list.txt')


if __name__ == '__main__':
    unittest.main()
