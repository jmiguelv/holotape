"""Safely enrich existing native Notion tasks from legacy Markdown exports.

Uses Python 3.9+ and the already-authenticated `ntn` CLI; installs nothing.
No workspace IDs, source exports, credentials, or migration state are bundled.
Run with --help for planning/apply options. Native source comments are not in
Markdown exports and are not fabricated by this tool.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import notion_markdown as md

STATE_SCHEMA = 'notion-task-migration/v1'
REPOSITORY = Path(__file__).resolve().parents[1]


def validate_id(value):
    return str(uuid.UUID(str(value)))


def check_state_path(path):
    path = Path(path).expanduser()
    if path.is_symlink() or path.resolve().is_relative_to(REPOSITORY):
        raise ValueError('Private migration state must be outside the checkout and not a symlink')
    if path.resolve().parent == Path(path.anchor):
        raise ValueError('Choose a dedicated directory for migration state')
    return path.resolve()


def save_state(path, state):
    path = check_state_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.notion-state-', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(state, stream, indent=2)
        stream.write('\n')
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def validate_media(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError('Attachment is missing or exceeds the free-plan upload limit')
    if path.suffix.lower() == '.png':
        with path.open('rb') as stream:
            if stream.read(8) != b'\x89PNG\r\n\x1a\n':
                raise ValueError('Invalid PNG signature')
        return 'image/png'
    if path.suffix.lower() == '.txt':
        _, warnings = md.sanitise_source(path.read_text(encoding='utf-8'))
        if warnings:
            raise ValueError('Text attachment contains credential material; not uploaded')
        return 'text/plain'
    raise ValueError('Only PNG images and plain-text attachments are supported')


def stable_body(block):
    body = copy.deepcopy(block[block['type']])
    if block['type'] in ('image', 'file') and body.get('type') == 'file':
        url = urlsplit(body['file']['url'])
        body['file']['url'] = urlunsplit(url._replace(query='', fragment=''))
        body['file'].pop('expiry_time', None)
    return body


def plain(block):
    return ''.join(x.get('plain_text', x.get('text', {}).get('content', '')) for x in block[block['type']].get('rich_text', []))


def is_legacy_stub(blocks):
    headings = [plain(b) for b in blocks if b['type'] == 'heading_2']
    return (len(blocks) >= 9 and headings == ['Work to track', 'Source and previous state', 'Tracking']
            and blocks[0]['type'] == 'heading_2' and blocks[1]['type'] == 'paragraph'
            and plain(blocks[1]).startswith(('Imported work item:', 'Track changes to the RSE Handbook.'))
            and all(not b.get('has_children') for b in blocks))


def shallow(blocks, depth=0):
    result = copy.deepcopy(blocks)
    for b in result:
        nested = b[b['type']].get('children')
        if nested:
            if depth >= 1:
                del b[b['type']]['children']
            else:
                b[b['type']]['children'] = shallow(nested, depth + 1)
    return result


class NotionClient:
    def __init__(self, workspace):
        self.workspace = validate_id(workspace)

    def request(self, method, path, body=None, extra=()):
        args = ['ntn', 'api', '-X', method, path, *extra]
        if body is not None:
            args += ['-d', json.dumps(body)]
        env = os.environ.copy()
        env['NOTION_WORKSPACE_ID'] = self.workspace
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
        if result.returncode:
            error, _ = md.sanitise_source(result.stderr)
            raise RuntimeError(method + ' ' + path + ': ' + error.strip())
        return json.loads(result.stdout)

    def listing(self, path, extra=()):
        rows, cursor = [], None
        while True:
            query = [*extra, 'page_size==100']
            if cursor:
                query.append('start_cursor==' + cursor)
            result = self.request('GET', path, extra=query)
            rows.extend(result['results'])
            if not result['has_more']:
                return rows
            cursor = result['next_cursor']
            if not cursor:
                raise RuntimeError('Missing pagination cursor')

    def page(self, page_id):
        return self.request('GET', '/v1/pages/' + validate_id(page_id))

    def children(self, block_id):
        return self.listing('/v1/blocks/' + validate_id(block_id) + '/children')

    def comments(self, block_id):
        return self.listing('/v1/comments', ('block_id==' + validate_id(block_id),))

    def verify(self, actual, expected):
        kind = expected['type']
        if actual['type'] != kind:
            raise RuntimeError('Block type differs after write')
        body = expected[kind]
        if 'rich_text' in body and md.rich_signature(actual[kind]['rich_text']) != md.rich_signature(body['rich_text']):
            raise RuntimeError('Block text or formatting differs after write')
        if kind in ('image', 'file'):
            if actual[kind]['type'] != 'file' or not actual[kind]['file']['url']:
                raise RuntimeError('Attachment did not become a hosted Notion file')
            if md.rich_signature(actual[kind]['caption']) != md.rich_signature(body['caption']):
                raise RuntimeError('Attachment caption differs after write')
        if kind == 'callout':
            if actual[kind]['icon'] != body['icon'] or actual[kind]['color'] != body['color']:
                raise RuntimeError('Callout icon or background differs after write')
        if kind == 'code' and actual[kind]['language'] != body['language']:
            raise RuntimeError('Code language differs after write')
        if kind == 'table':
            for key in ('table_width', 'has_column_header', 'has_row_header'):
                if actual[kind][key] != body[key]:
                    raise RuntimeError('Table structure differs after write')
        if kind == 'table_row' and [md.rich_signature(x) for x in actual[kind]['cells']] != [md.rich_signature(x) for x in body['cells']]:
            raise RuntimeError('Table cells differ after write')
        if 'children' in body:
            rows = self.children(actual['id'])
            if len(rows) != len(body['children']):
                raise RuntimeError('Nested block count differs after write')
            for child, wanted in zip(rows, body['children']):
                self.verify(child, wanted)

    def complete_tree(self, actual, expected, record=None):
        wanted = expected[expected['type']].get('children', [])
        if not wanted:
            return
        rows = self.children(actual['id'])
        if not rows:
            self.append(actual['id'], wanted, record=record)
            return
        if len(rows) != len(wanted):
            raise RuntimeError('Partial nested content; inspect before retrying')
        for child, expected_child in zip(rows, wanted):
            if record:
                record(child)
            self.complete_tree(child, expected_child, record)

    def append(self, parent, blocks, after=None, record=None):
        before = {b['id'] for b in self.children(parent)}
        body = {'children': shallow(blocks)}
        if after:
            body['position'] = {'type': 'after_block', 'after_block': {'id': validate_id(after)}}
        self.request('PATCH', '/v1/blocks/' + validate_id(parent) + '/children', body)
        added = [b for b in self.children(parent) if b['id'] not in before]
        if record:
            for b in added:
                record(b)
        if len(added) != len(blocks):
            raise RuntimeError('Unexpected inserted block count; inspect before retrying')
        for actual, expected in zip(added, blocks):
            self.complete_tree(actual, expected, record)
            self.verify(actual, expected)
        return added
