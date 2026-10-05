#!/usr/bin/env python3
"""Validate canonical HTML, hreflang, llms.txt, robots.txt and sitemap.xml."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import re
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
origin = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else None
if not origin:
    raise SystemExit('usage: python3 validate-discovery.py https://host.ataraxydigital.com')
errors = []

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical, self.describedby, self.alternates, self.ids = [], [], {}, set()
        self.noindex = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.add(a['id'])
        if tag == 'link':
            rel = a.get('rel', '').split()
            if 'canonical' in rel:
                self.canonical.append(a.get('href'))
            if 'describedby' in rel:
                self.describedby.append((a.get('href'), a.get('type')))
            if 'alternate' in rel and a.get('hreflang'):
                self.alternates[a['hreflang']] = a.get('href')
        if tag == 'meta' and a.get('name') == 'robots' and 'noindex' in a.get('content', '').lower():
            self.noindex = True

pages = {}
for file in root.rglob('index.html'):
    if any(part in {'tools', 'node_modules', '.next'} for part in file.relative_to(root).parts):
        continue
    path = file.relative_to(root).parent.as_posix()
    url = origin + ('/' if path == '.' else '/' + path + '/')
    page = Page()
    page.feed(file.read_text())
    if page.canonical != [url]:
        errors.append(f'{file}: canonical {page.canonical}, expected {url}')
    if page.describedby != [(origin + '/llms.txt', 'text/markdown')]:
        errors.append(f'{file}: describedby {page.describedby}')
    if page.noindex:
        errors.append(f'{file}: noindex')
    pages[url] = page

for url, page in pages.items():
    for lang, target in page.alternates.items():
        if target not in pages:
            errors.append(f'{url}: {lang} target missing: {target}')
        elif pages[target].alternates != page.alternates:
            errors.append(f'{url}: nonreciprocal hreflang for {target}')

try:
    tree = ET.parse(root / 'sitemap.xml')
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'x': 'http://www.w3.org/1999/xhtml'}
    mapped = {}
    for item in tree.findall('s:url', ns):
        loc = item.findtext('s:loc', namespaces=ns)
        mapped[loc] = {a.attrib['hreflang']: a.attrib['href'] for a in item.findall('x:link', ns)}
    if set(mapped) != set(pages):
        errors.append(f'sitemap URLs differ: missing={sorted(set(pages)-set(mapped))}, extra={sorted(set(mapped)-set(pages))}')
    for url in set(mapped) & set(pages):
        if mapped[url] != pages[url].alternates:
            errors.append(f'{url}: sitemap hreflang differs from HTML')
except (ET.ParseError, OSError) as exc:
    errors.append(f'sitemap.xml: {exc}')

robots = (root / 'robots.txt').read_text()
if f'Sitemap: {origin}/sitemap.xml' not in robots:
    errors.append('robots.txt: wrong or missing sitemap')
llms = (root / 'llms.txt').read_text()
if len(re.findall(r'^# ', llms, re.M)) != 1:
    errors.append('llms.txt: expected one H1')
for target in re.findall(r'\]\((https?://[^)]+)\)', llms):
    parts = urlsplit(target)
    if parts.scheme + '://' + parts.netloc != origin:
        continue
    path = parts.path or '/'
    if path.endswith('/'):
        path += 'index.html'
    if not (root / path.lstrip('/')).exists():
        errors.append(f'llms.txt: missing destination {target}')
    if parts.fragment and (origin + parts.path) in pages and parts.fragment not in pages[origin + parts.path].ids:
        errors.append(f'llms.txt: missing anchor {target}')

if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print(f'OK: {len(pages)} HTML pages; canonical, describedby, hreflang, sitemap, robots and llms.txt')
