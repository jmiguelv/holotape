import copy
import os
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


if __name__ == '__main__':
    unittest.main()
