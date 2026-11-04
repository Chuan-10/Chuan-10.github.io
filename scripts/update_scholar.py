#!/usr/bin/env python3
"""Save counts for selected publications from a public Scholar profile."""

import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

AUTHOR_ID = 'N1Imm0oAAAAJ'
ARTICLE_IDS = ('ufrVoPGSRksC', 'UeHWp8X0CEIC', 'Tyk-4Ss8FVUC', 'qjMakFHDy7sC')
MAX_BYTES = 2_000_000
MAX_COUNT = 2**53 - 1


class UpdateError(Exception):
    pass


class ProfileParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.row = None
        self.in_count = False
        self.counts = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = attributes.get('class', '').split()
        if tag == 'tr' and 'gsc_a_tr' in classes:
            self.row = {'id': None, 'has_count_cell': False, 'count': []}
        elif self.row is not None:
            if tag == 'a' and 'gsc_a_at' in classes:
                query = parse_qs(urlsplit(attributes.get('href', '')).query)
                full_id = query.get('citation_for_view', [''])[0]
                if full_id.startswith(AUTHOR_ID + ':'):
                    self.row['id'] = full_id[len(AUTHOR_ID) + 1:]
            elif tag == 'td' and 'gsc_a_c' in classes:
                self.row['has_count_cell'] = True
                self.in_count = True

    def handle_data(self, data):
        if self.row is not None and self.in_count:
            self.row['count'].append(data)

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_count = False
        if tag == 'tr' and self.row is not None:
            article_id = self.row['id']
            if article_id in ARTICLE_IDS:
                if not self.row['has_count_cell'] or article_id in self.counts:
                    raise UpdateError('Missing or duplicate citation cell')
                text = re.sub(r'[\s,]', '', ''.join(self.row['count']))
                if text and (not text.isascii() or not text.isdigit()):
                    raise UpdateError('Unexpected citation count')
                self.counts[article_id] = int(text) if text else 0
            self.row = None


def fetch(url, label):
    request = Request(url, headers={'User-Agent': 'Academic-Homepage-Metrics/1.0', 'Accept': 'text/html,application/json'})
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise UpdateError(f'{label} returned HTTP {exc.code}') from None
    except (URLError, TimeoutError, OSError):
        raise UpdateError(f'{label} could not be reached') from None
    if len(body) > MAX_BYTES:
        raise UpdateError(f'{label} response was too large')
    return body.decode('utf-8', errors='replace')


def direct_counts():
    # This public profile URL is allowed by Google Scholar's robots.txt.
    query = urlencode({'user': AUTHOR_ID, 'hl': 'en', 'pagesize': '100'})
    html = fetch('https://scholar.google.com/citations?' + query, 'Google Scholar')
    parser = ProfileParser()
    parser.feed(html)
    return parser.counts


def serpapi_counts(key):
    query = urlencode({
        'engine': 'google_scholar_author', 'author_id': AUTHOR_ID,
        'hl': 'en', 'num': '100', 'api_key': key
    })
    try:
        payload = json.loads(fetch('https://serpapi.com/search.json?' + query, 'SerpApi'))
    except (ValueError, TypeError):
        raise UpdateError('SerpApi returned invalid JSON') from None
    if not isinstance(payload, dict):
        raise UpdateError('SerpApi returned an unexpected response')
    articles = payload.get('articles')
    if not isinstance(articles, list):
        raise UpdateError('SerpApi did not return an article list')
    counts = {}
    for article in articles:
        if not isinstance(article, dict):
            continue
        full_id = article.get('citation_id', '')
        if not isinstance(full_id, str):
            continue
        if not full_id.startswith(AUTHOR_ID + ':'):
            continue
        article_id = full_id[len(AUTHOR_ID) + 1:]
        if article_id in ARTICLE_IDS:
            if article_id in counts:
                raise UpdateError('SerpApi returned a duplicate article')
            cited_by = article.get('cited_by', {})
            counts[article_id] = cited_by.get('value', 0) if isinstance(cited_by, dict) else None
    return counts


def validate(counts):
    if set(counts) != set(ARTICLE_IDS):
        raise UpdateError('Google Scholar did not return all four selected records')
    if any(type(value) is not int or not 0 <= value <= MAX_COUNT for value in counts.values()):
        raise UpdateError('Google Scholar returned an invalid citation count')


def main(output):
    key = os.environ.get('SERPAPI_API_KEY', '').strip()
    counts = serpapi_counts(key) if key else direct_counts()
    validate(counts)
    result = {
        'source': 'Google Scholar',
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'citations': {article_id: counts[article_id] for article_id in ARTICLE_IDS},
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(target)
    print('Updated Google Scholar citations for four records.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: update_scholar.py OUTPUT_JSON')
    try:
        main(sys.argv[1])
    except (UpdateError, OSError) as error:
        print(f'Citation update failed: {error}', file=sys.stderr)
        raise SystemExit(1)
