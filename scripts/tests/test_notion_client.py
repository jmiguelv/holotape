import copy
import stat
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import notion_migrate as migration

ID = '11111111-1111-4111-8111-111111111111'


class SafetyTests(unittest.TestCase):
    def test_ids_are_validated_before_becoming_api_paths(self):
        self.assertEqual(migration.validate_id(ID.replace('-', '')), ID)
        with self.assertRaises(ValueError):
            migration.validate_id('../other-page')

    def test_private_state_cannot_be_written_inside_checkout(self):
        with self.assertRaises(ValueError):
            migration.check_state_path(Path(__file__).resolve().parents[2] / 'private-state.json')

    def test_state_is_private_and_identifies_its_own_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            migration.save_state(path, {'schema': migration.STATE_SCHEMA, 'task_id': ID})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_png_signature_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'figure.png'
            path.write_bytes(b'not an image')
            with self.assertRaises(ValueError):
                migration.validate_media(path)

    def test_text_attachment_with_credentials_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'list.txt'
            path.write_text('password: EXAMPLE_ONLY')
            with self.assertRaises(ValueError) as caught:
                migration.validate_media(path)
            self.assertNotIn('EXAMPLE_ONLY', str(caught.exception))

    def test_expiring_download_urls_do_not_look_like_content_edits(self):
        def image(query):
            return {'type': 'image', 'image': {'type': 'file', 'file': {'url': 'https://files.example/asset.png?' + query, 'expiry_time': query}}}
        self.assertEqual(migration.stable_body(image('old')), migration.stable_body(image('new')))

    def test_user_content_is_not_treated_as_legacy_metadata_stub(self):
        self.assertFalse(migration.is_legacy_stub([{'type': 'paragraph', 'paragraph': {'rich_text': []}}]))


class MemoryClient(migration.NotionClient):
    def __init__(self):
        self.workspace = ID
        self.blocks = {ID: []}

    def children(self, block_id):
        return copy.deepcopy(self.blocks.get(block_id, []))

    def request(self, method, path, body=None, extra=()):
        self.assert_method = method
        parent = path.split('/')[3]
        assert method == 'PATCH' and path.endswith('/children')
        def create(request):
            b = copy.deepcopy(request)
            b['id'] = str(uuid.uuid4())
            nested = b[b['type']].pop('children', [])
            self.blocks[b['id']] = [create(child) for child in nested]
            return b
        self.blocks.setdefault(parent, []).extend(create(b) for b in body['children'])
        # The real backend may return pre-existing blocks as well.
        return {'results': self.children(parent)}


class AppendTests(unittest.TestCase):
    def test_append_counts_only_new_ids_and_preserves_deep_children(self):
        client = MemoryClient()
        client.blocks[ID].append({'id': str(uuid.uuid4()), 'type': 'paragraph', 'paragraph': {'rich_text': []}})
        leaf = {'object': 'block', 'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': []}}
        nested = copy.deepcopy(leaf)
        nested['bulleted_list_item']['children'] = [copy.deepcopy(leaf)]
        root = copy.deepcopy(leaf)
        root['bulleted_list_item']['children'] = [nested]
        before = copy.deepcopy(root)
        created = client.append(ID, [root])
        self.assertEqual(len(created), 1)
        self.assertEqual(root, before)
        direct = client.children(created[0]['id'])
        self.assertEqual(len(client.children(direct[0]['id'])), 1)


class PlanTests(unittest.TestCase):
    def test_empty_export_has_three_sections_without_invented_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Example.md'
            path.write_text('# Example\n\nStatus: Not started')
            plan = migration.build_plan({'source': str(path), 'task': ID})
            headings = [b['heading_2']['rich_text'][0]['text']['content'] for b in plan['blocks'] if b['type'] == 'heading_2']
            self.assertEqual(headings, ['Purpose and outcome', 'Context and resources', 'Work log'])
            self.assertEqual(plan['document']['actions'], [])
            self.assertNotIn('Completed', str(plan['blocks']))

    def test_link_mapping_and_redaction_happen_before_a_plan_is_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Example.md'
            path.write_text('# Example\n\n8 October 2026\n\n[Related](Related%20task.md)\npassword: EXAMPLE_ONLY')
            plan = migration.build_plan({'source': str(path), 'task': ID, 'links': {'Related%20task.md': 'https://example.com/task'}})
            self.assertNotIn('EXAMPLE_ONLY', str(plan))
            self.assertNotIn('Related%20task.md', str(plan['blocks']))
            self.assertTrue(plan['document']['warnings'])

    def test_forbidden_terms_in_actions_are_checked_too(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Example.md'
            path.write_text('# Example\n\n- [ ] restricted-label')
            with self.assertRaises(ValueError):
                migration.build_plan({'source': str(path), 'task': ID, 'forbid_words': ['restricted-label']})

    def test_api_rich_text_limit_is_checked_before_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Example.md'
            path.write_text('# Example\n\n```python\n' + 'x' * 190001 + '\n```')
            with self.assertRaises(ValueError):
                migration.build_plan({'source': str(path), 'task': ID})

    def test_changed_plan_is_not_silently_reported_as_already_imported(self):
        class NoRequests:
            workspace = ID
            def page(self, value):
                raise AssertionError('No API request is allowed')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Example.md'
            path.write_text('# Example')
            job = {'source': str(path), 'task': ID}
            plan = migration.build_plan(job)
            state = {'schema': migration.STATE_SCHEMA, 'task': ID, 'workspace': ID,
                     'source_sha256': plan['source_sha256'], 'plan_fingerprint': 'different', 'verified': True}
            state_path = Path(folder) / 'state.json'
            migration.save_state(state_path, state)
            with self.assertRaises(ValueError):
                migration.migrate(NoRequests(), job, state_path)

    def test_title_mentions_do_not_require_a_text_field(self):
        page = {'properties': {'Name': {'type': 'title', 'title': [{'plain_text': 'Today', 'type': 'mention', 'mention': {}}]}}}
        self.assertEqual(migration.source_title(page), 'Today')

    def test_live_user_content_is_refused_before_any_write(self):
        class ReadOnlyClient:
            workspace = ID
            def page(self, value):
                return {'id': ID, 'properties': {}, 'in_trash': False}
            def children(self, value):
                return [{'type': 'paragraph', 'paragraph': {'rich_text': []}}]
            def request(self, *args, **kwargs):
                raise AssertionError('No mutation is allowed')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Example.md'
            path.write_text('# Example')
            with self.assertRaises(ValueError):
                migration.migrate(ReadOnlyClient(), {'source': str(path), 'task': ID}, Path(folder) / 'state.json')


if __name__ == '__main__':
    unittest.main()
