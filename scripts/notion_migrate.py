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


def source_title(page):
    return ''.join(x.get('plain_text', x['text']['content']) for prop in page['properties'].values()
                   if prop['type'] == 'title' for x in prop['title'])


def native_fields(page):
    suffixes = {'parent': 'parent_task_relation', 'parts': 'sub_task_relation',
                'project': 'task_to_project_relation', 'status': 'status_property',
                'assignee': 'assign_property', 'due': 'due_date_property', 'priority': 'priority_property'}
    result = {}
    for role, suffix in suffixes.items():
        uri = 'notion://tasks/' + suffix
        found = next((v for v in page['properties'].values() if unquote(v['id']) == uri), None)
        if found is None:
            raise ValueError('Task is missing native field: ' + role)
        result[role] = found
    result['title'] = next(v for v in page['properties'].values() if v['type'] == 'title')
    return result


def build_plan(job):
    path = Path(job['source']).expanduser().resolve()
    if path.suffix.lower() != '.md' or path.stat().st_size > 2_000_000:
        raise ValueError('Expected a Markdown export smaller than 2 MB')
    raw = path.read_text(encoding='utf-8')
    document = md.prepare_export(raw)
    task_id = validate_id(job['task'])
    self_url = 'https://app.notion.com/p/' + task_id.replace('-', '')
    links = dict(job.get('links', {}))
    links.setdefault(path.name.replace(' ', '%20'), self_url)
    def rewrite(value):
        for old, new in links.items():
            value = value.replace(old, new)
        for old, new in job.get('terms', {}).items():
            value = value.replace(old, new)
        return value
    context = rewrite(document['context'])
    context = re.sub(r'^#{1,2} ', '### ', context, flags=re.M)
    log = rewrite(document['log'])
    identity = re.search(r'([a-f0-9]{32})\.md$', path.name, re.I)
    source_url = job.get('source_url') or ('https://app.notion.com/p/' + identity[1] if identity else None)
    citation = '[exported task](' + source_url + ')' if source_url else 'supplied Markdown export'
    purpose = job.get('purpose') or document['title']
    blocks = [md.block('heading_2', 'Purpose and outcome'), md.block('paragraph', purpose),
              md.block('heading_2', 'Context and resources'),
              md.block('paragraph', 'Source: ' + citation + '. Source statements and dates are historical, not an automatic update to current task properties.')]
    if document['metadata']:
        summary = 'Source-listed metadata: ' + '; '.join(k + ': ' + rewrite(v) for k, v in document['metadata'].items())
        blocks.append({'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': md.text(summary)}})
    blocks.extend(md.render(context, source_file=path))
    if not context:
        blocks.append(md.block('paragraph', 'No additional background or resource notes were supplied in the export.'))
    blocks.append(md.block('heading_2', 'Work log'))
    blocks.extend(md.render(log, source_file=path) if log else [md.block('paragraph', 'No dated work-log entries were supplied in the export.')])
    titles = job.get('action_titles')
    if titles is not None and len(titles) != len(document['actions']):
        raise ValueError('Action-title overrides must match the explicit source checkbox count')
    for index, action in enumerate(document['actions']):
        action['original'] = rewrite(action['original'])
        action['title'] = titles[index] if titles else ''.join(x['text']['content'] for x in md.rich(action['original']))
        if re.search(r'\bby today\b', action['original'], re.I):
            document['warnings'].append('Relative deadline left unresolved for source action ' + str(index + 1))
    for b in md.walk(blocks):
        if '_asset' in b[b['type']]:
            validate_media(md.safe_asset(path, b[b['type']]['_asset']))
        for item in b[b['type']].get('rich_text', []):
            link = (item.get('text', {}).get('link') or {}).get('url')
            if link and (urlsplit(link).scheme not in ('http', 'https') or not urlsplit(link).netloc or urlsplit(link).username):
                raise ValueError('Unresolved or unsafe link; supply an explicit link mapping')
    serialised = json.dumps(blocks, ensure_ascii=False)
    for forbidden in job.get('forbid_words', []):
        if forbidden.casefold() in serialised.casefold():
            raise ValueError('Forbidden workspace terminology remains in the plan')
    return {'source': str(path), 'task': task_id, 'source_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'document': document, 'blocks': blocks, 'source_url': source_url}


def copy_paragraph(block):
    if block['type'] not in ('paragraph', 'bulleted_list_item'):
        raise ValueError('Extra live content requires manual review before migration')
    body = {'rich_text': []}
    for item in block[block['type']]['rich_text']:
        if item['type'] != 'text':
            raise ValueError('Extra live mentions require manual review before migration')
        new = {'type': 'text', 'text': copy.deepcopy(item['text'])}
        if 'annotations' in item:
            new['annotations'] = copy.deepcopy(item['annotations'])
        body['rich_text'].append(new)
    return {'object': 'block', 'type': block['type'], block['type']: body}


def migrate(client, job, state_path):
    plan = build_plan(job)
    state_path = check_state_path(state_path)
    if state_path.exists():
        old = json.loads(state_path.read_text())
        if (old.get('schema') == STATE_SCHEMA and old.get('task') == plan['task']
                and old.get('workspace') == client.workspace and old.get('source_sha256') == plan['source_sha256']
                and old.get('verified')):
            return old
        raise ValueError('Existing or partial state requires inspection; no requests repeated')
    page = client.page(plan['task'])
    old_blocks = client.children(plan['task'])
    if page.get('in_trash') or not is_legacy_stub(old_blocks):
        raise ValueError('Target is not an untouched legacy metadata stub; refusing to overwrite user content')
    fields = native_fields(page)
    if fields['parts']['relation'] or fields['parts'].get('has_more'):
        raise ValueError('Target already has subtasks; reconcile before importing')
    for b in old_blocks:
        if b['parent'].get('page_id') != plan['task'] or client.comments(b['id']):
            raise ValueError('Existing block ownership or comments require review before replacement')
    old_comments = client.comments(plan['task'])
    data_source = validate_id(page['parent']['data_source_id'])
    # Preserve extra existing warnings/links, such as the OCR-overlap note.
    extras = [copy_paragraph(b) for b in old_blocks[9:]]
    log_index = next(i for i, b in enumerate(plan['blocks']) if b['type'] == 'heading_2' and plain(b) == 'Work log')
    plan['blocks'][log_index:log_index] = extras
    state = {'schema': STATE_SCHEMA, 'workspace': client.workspace, 'task': plan['task'],
             'source_sha256': plan['source_sha256'], 'before_page': page, 'before_blocks': old_blocks,
             'before_comments': old_comments, 'warnings': plan['document']['warnings'],
             'uploads': [], 'actions': [], 'created_blocks': [], 'removed_blocks': [], 'verified': False}
    def save():
        save_state(state_path, state)
    def record(b):
        if b['id'] not in state['created_blocks']:
            state['created_blocks'].append(b['id'])
            save()
    def mutate(method, path, body=None, extra=()):
        state['pending_operation'] = {'method': method, 'path': path}
        save()
        result = client.request(method, path, body, extra)
        state.pop('pending_operation', None)
        save()
        return result
    save()
    for b in md.walk(plan['blocks']):
        reference = b[b['type']].pop('_asset', None)
        if reference is None:
            continue
        asset = md.safe_asset(plan['source'], reference)
        mime = validate_media(asset)
        upload = mutate('POST', '/v1/file_uploads', {'mode': 'single_part', 'filename': asset.name, 'content_type': mime})
        upload_id = validate_id(upload['id'])
        state['uploads'].append({'id': upload_id, 'filename': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()})
        save()
        mutate('POST', '/v1/file_uploads/' + upload_id + '/send', extra=('--file', str(asset)))
        uploaded = client.request('GET', '/v1/file_uploads/' + upload_id)
        if uploaded['status'] != 'uploaded' or uploaded['content_length'] != asset.stat().st_size:
            raise RuntimeError('Upload did not complete as expected')
        b[b['type']].update({'type': 'file_upload', 'file_upload': {'id': upload_id}})
    projects = copy.deepcopy(fields['project']['relation'])
    for action in plan['document']['actions']:
        parent = state['actions'][action['parent']]['id'] if action['parent'] is not None else plan['task']
        status = 'Done' if action['done'] else 'Not Started'
        properties = {fields['title']['id']: {'title': md.text(action['title'])},
                      fields['parent']['id']: {'relation': [{'id': parent}]}, fields['project']['id']: {'relation': projects},
                      fields['status']['id']: {'status': {'name': status}}, fields['assignee']['id']: {'people': []},
                      fields['due']['id']: {'date': {'start': action['due']} if action['due'] else None},
                      fields['priority']['id']: {'select': None}}
        if 'Completed on' in page['properties']:
            properties[page['properties']['Completed on']['id']] = {'date': None}
        details = [md.block('paragraph', action['original']),
                   md.block('paragraph', 'Explicit source checkbox; state is preserved from the export, not newly verified. Original names are source attribution, not automatic current assignments. Relative dates are not inferred.'),
                   md.block('paragraph', 'Source: ' + ('[exported task](' + plan['source_url'] + ')' if plan['source_url'] else 'supplied Markdown export') + '.')]
        if action['source_date']:
            details.append(md.block('paragraph', 'Source log section: ' + action['source_date']))
        child = mutate('POST', '/v1/pages', {'parent': {'type': 'data_source_id', 'data_source_id': data_source},
                                          'properties': properties, 'children': details})
        child_id = validate_id(child['id'])
        state['actions'].append({'id': child_id, 'parent': parent, 'status': status, 'due': action['due'], 'original': action['original']})
        save()
        props = client.page(child_id)['properties']
        child_fields = native_fields({'properties': props})
        if child_fields['status']['status']['name'] != status or {x['id'] for x in child_fields['parent']['relation']} != {parent}:
            raise RuntimeError('Subtask status or parent differs after creation')
        if child_fields['project']['relation'] != projects or child_fields['assignee']['people']:
            raise RuntimeError('Subtask effort or assignment differs after creation')
        if (child_fields['due']['date']['start'] if child_fields['due']['date'] else None) != action['due']:
            raise RuntimeError('Historical subtask deadline differs after creation')
        client.verify(client.children(child_id)[0], details[0])
    # Recheck before inserting. No source status/assignee is applied to the parent.
    if client.children(plan['task']) != old_blocks:
        raise RuntimeError('Target changed during preparation; source content not replaced')
    roots = []
    anchor = None
    for offset in range(0, len(plan['blocks']), 20):
        state['pending_operation'] = {'method': 'PATCH', 'path': '/v1/blocks/' + plan['task'] + '/children'}
        save()
        added = client.append(plan['task'], plan['blocks'][offset:offset + 20], after=anchor, record=record)
        roots.extend(b['id'] for b in added)
        anchor = added[-1]['id']
        state.pop('pending_operation', None)
        save()
    for old in old_blocks:
        current = client.request('GET', '/v1/blocks/' + validate_id(old['id']))
        if stable_body(current) != stable_body(old) or client.comments(old['id']):
            raise RuntimeError('Old block changed; keep it and inspect before removing')
        mutate('DELETE', '/v1/blocks/' + validate_id(old['id']))
        state['removed_blocks'].append(old['id'])
        save()
    final_page = client.page(plan['task'])
    for key, value in page['properties'].items():
        if value['id'] != fields['parts']['id'] and final_page['properties'][key] != value:
            raise RuntimeError('Existing task properties changed during import')
    direct = {x['id'] for x in native_fields(final_page)['parts']['relation']}
    expected = {x['id'] for x in state['actions'] if x['parent'] == plan['task']}
    if direct != expected:
        raise RuntimeError('Root subtask relations differ after import')
    final = client.children(plan['task'])
    if [b['id'] for b in final] != roots:
        raise RuntimeError('Final task block order differs from the approved plan')
    for b, wanted in zip(final, plan['blocks']):
        client.verify(b, wanted)
    if client.comments(plan['task']) != old_comments:
        raise RuntimeError('Existing page comments changed')
    state['counts'] = {'actions': len(state['actions']), 'uploads': len(state['uploads']),
                       'dated_entries': sum(b['type'] == 'heading_3' and any(x['type'] == 'mention' for x in b['heading_3']['rich_text']) for b in md.walk(plan['blocks']))}
    state['verified'] = True
    save()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog='Job JSON: source, task, optional purpose, links, terms, forbid_words, action_titles. Use an object or an explicit list of objects. Keep jobs/state outside the checkout. Default is offline dry-run; --apply performs writes. Partial state stops reruns for manual recovery. Native comments require a separate source connection.')
    parser.add_argument('--job', type=Path, required=True, help='Private JSON job or explicit job list')
    parser.add_argument('--workspace', default=os.environ.get('NOTION_WORKSPACE_ID'))
    parser.add_argument('--state-dir', type=Path, help='Private, external directory for backups and operation journals')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    jobs = json.loads(args.job.read_text())
    jobs = jobs if isinstance(jobs, list) else [jobs]
    client = None
    if args.apply:
        if not args.workspace or not args.state_dir:
            parser.error('--apply requires an explicit workspace and external --state-dir')
        client = NotionClient(args.workspace)
    for job in jobs:
        plan = build_plan(job)
        summary = {'task': plan['document']['title'], 'actions': len(plan['document']['actions']), 'warnings': plan['document']['warnings']}
        if client:
            state = migrate(client, job, args.state_dir / (plan['task'] + '.json'))
            summary.update(state['counts'])
            summary['verified'] = state['verified']
        print(json.dumps(summary))


if __name__ == '__main__':
    main()
