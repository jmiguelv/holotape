"""Convert legacy Notion Markdown to block requests without executing source code.

Python 3.9+; standard library only. Export content and credentials are not bundled.
Native comment threads are not part of Markdown exports.
"""

import copy
import datetime
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


TOKEN = re.compile(r'(?P<ticks>`{1,2})(?P<code>.+?)(?P=ticks)|\[([^\]]+)\]\(([^)]+)\)|\*\*(.+?)\*\*|~~(.+?)~~|\*([^*]+)\*|https?://[^\s<>]+')

def text(value, url=None, style=None):
    items = []
    for pos in range(0, len(value), 1900):
        item = {'type': 'text', 'text': {'content': value[pos:pos + 1900]}}
        if url:
            item['text']['link'] = {'url': url}
        if style:
            item['annotations'] = {style: True}
        items.append(item)
    return items

def rich(value):
    result = []
    pos = 0
    for m in TOKEN.finditer(value):
        result += text(value[pos:m.start()])
        ticks, code, label, url, bold, struck, italic = m.groups()
        if code is not None:
            result += text(code, style='code')
        elif label is not None:
            styled = label.startswith('`') and label.endswith('`')
            result += text(label.strip('`') if styled else label, url, 'code' if styled else None)
        elif bold is not None:
            result += text(bold, style='bold')
        elif struck is not None:
            result += text(struck, style='strikethrough')
        elif italic is not None:
            result += text(italic, style='italic')
        else:
            value_url = m.group().rstrip('.,')
            result += text(value_url, value_url)
            result += text(m.group()[len(value_url):])
        pos = m.end()
    result += text(value[pos:])
    return result

def block(kind, value):
    return {'object': 'block', 'type': kind, kind: {'rich_text': rich(value)}}

def callout(value, emoji='ℹ️', icon=None):
    b = block('callout', value)
    b['callout']['icon'] = icon if icon is not None else {'type': 'emoji', 'emoji': emoji}
    b['callout']['color'] = 'yellow_background'
    return b

def parse_aside(lines):
    value = '\n'.join(lines).strip()
    icon = None
    if value.lower().startswith('<img'):
        image = re.match(r'<img\b[^>]*>', value, re.IGNORECASE | re.DOTALL)
        if image is None:
            raise ValueError('Unclosed callout icon tag')

        class IconParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == 'img':
                    self.src = dict(attrs).get('src')

        parser = IconParser()
        parser.src = None
        parser.feed(image.group())
        parser.close()
        url = urlsplit(parser.src or '')
        if url.scheme != 'https' or not url.netloc:
            raise ValueError('Callout icon requires an HTTPS URL or a separate file upload')
        icon = {'type': 'external', 'external': {'url': parser.src}}
        value = value[image.end():].strip()
    elif value:
        marker = value.splitlines()[0].strip()
        if marker and any(unicodedata.category(c) == 'So' for c in marker) and all(unicodedata.category(c) in ('So', 'Sk', 'Mn', 'Me') or c == '\u200d' for c in marker):
            icon = {'type': 'emoji', 'emoji': marker}
            value = value[len(value.splitlines()[0]):].strip()
    return callout(value, icon=icon)

def date_heading(value):
    dates = [datetime.datetime.strptime(x.strip(), '%d %B %Y').date().isoformat() for x in value.split(',')]
    obj = {'start': dates[0]}
    if len(dates) > 1:
        assert len(dates) == 2
        obj['end'] = dates[1]
    return {'object': 'block', 'type': 'heading_3', 'heading_3': {'rich_text': [{'type': 'mention', 'mention': {'type': 'date', 'date': obj}}]}}

def render(markdown):
    lines = markdown.splitlines()
    result = []
    stack = []
    i = 0
    while i < len(lines):
        original = lines[i]
        stripped = original.strip()
        indent = len(original) - len(original.lstrip())
        i += 1
        if not stripped or stripped == '---':
            continue
        if stripped.startswith('```'):
            language = stripped[3:].strip() or 'plain text'
            assert language in ('json', 'bash', 'mermaid', 'plain text')
            content = []
            while i < len(lines) and not re.fullmatch(r'\s*```\s*', lines[i]):
                content.append(lines[i][indent:] if lines[i].startswith(' ' * indent) else lines[i])
                i += 1
            assert i < len(lines), 'Unclosed code fence'
            i += 1
            b = {'object': 'block', 'type': 'code', 'code': {'rich_text': text('\n'.join(content)), 'language': language}}
        elif stripped == '<aside>':
            content = []
            while i < len(lines) and lines[i].strip() != '</aside>':
                content.append(lines[i])
                i += 1
            assert i < len(lines), 'Unclosed aside'
            i += 1
            b = parse_aside(content)
        elif stripped.startswith('!['):
            image = re.fullmatch(r'!\[([^\]]+)\]\(([^)]+)\)', stripped)
            assert image
            filename = Path(unquote(image[2])).name
            assert (FILE.parent / unquote(image[2])).is_file()
            b = {'object': 'block', 'type': 'image', 'image': {'_filename': filename, 'caption': rich(image[1])}}
        elif stripped.startswith('|'):
            entries = [stripped]
            while i < len(lines) and (lines[i].strip().startswith('|') or not entries[-1].endswith('|')):
                part = lines[i].strip()
                if entries[-1].endswith('|'):
                    entries.append(part)
                else:
                    entries[-1] += '\n' + part
                i += 1
            rows = []
            width = None
            for entry in entries:
                assert entry.endswith('|')
                cells = [x.strip() for x in entry.strip('|').split('|')]
                if all(re.fullmatch(r':?-+:?', x) for x in cells):
                    continue
                if width is None:
                    width = len(cells)
                assert len(cells) == width, cells
                rows.append({'object': 'block', 'type': 'table_row', 'table_row': {'cells': [rich(c) for c in cells]}})
            b = {'object': 'block', 'type': 'table', 'table': {'table_width': width, 'has_column_header': True, 'has_row_header': False, 'children': rows}}
        elif re.match(r'^## \d', stripped):
            b = date_heading(stripped[3:])
            stack = []
        elif stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            b = block('heading_3' if level >= 3 else 'heading_2', stripped.lstrip('#').strip())
            stack = []
        elif stripped.startswith('- ') or re.match(r'^\d+\. ', stripped):
            assert not re.match(r'^- \[[ xX]\]', stripped), 'Actions must not be rendered as checklist blocks.'
            numbered = re.match(r'^\d+\. (.*)', stripped)
            kind = 'numbered_list_item' if numbered else 'bulleted_list_item'
            b = block(kind, numbered[1] if numbered else stripped[2:])
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                parent = stack[-1][1]
                parent[parent['type']].setdefault('children', []).append(b)
            else:
                result.append(b)
            stack.append((indent, b))
            continue
        else:
            content = [stripped]
            while i < len(lines) and lines[i].strip() and not re.match(r'^\s*(?:#|\||- |!\[|```|<aside>|---|\d+\. )', lines[i]):
                content.append(lines[i].strip())
                i += 1
            b = block('paragraph', '\n'.join(content))
        if stack and indent > stack[-1][0]:
            parent = stack[-1][1]
            parent[parent['type']].setdefault('children', []).append(b)
        else:
            result.append(b)
            if indent == 0:
                stack = []
    return result

def walk(blocks):
    for b in blocks:
        yield b
        yield from walk(b[b['type']].get('children', []))

def rich_signature(items):
    result = []
    for x in items:
        annotations = tuple(sorted(k for k, v in x.get('annotations', {}).items() if v is True))
        if x['type'] == 'text':
            link = (x['text'].get('link') or {}).get('url')
            if link:
                parsed = urlsplit(link)
                if parsed.scheme in ('http', 'https') and not parsed.path:
                    link = urlunsplit(parsed._replace(path='/'))
            result.append(('text', x['text']['content'], link, annotations))
        else:
            assert x['type'] == 'mention' and x['mention']['type'] == 'date'
            result.append(('date', x['mention']['date']['start'], x['mention']['date'].get('end')))
    normalised = []
    for item in result:
        if item[0] == 'text' and normalised and normalised[-1][0] == 'text' and item[2:] == normalised[-1][2:]:
            previous = normalised.pop()
            normalised.append(('text', previous[1] + item[1], *item[2:]))
        else:
            normalised.append(item)
    return normalised
