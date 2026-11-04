#!/usr/bin/env python3
"""Refresh selected-paper star counts and publish only the homepage."""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from publish_scholar import ALLOWED_REMOTES, PublishError, REPOSITORY, git

BRANCH = 'main'
PAPER = re.compile(
    r'<p class="paper-metrics" data-repo="(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"[^>]*>.*?</p>',
    re.DOTALL,
)
STAR_LINK = re.compile(r'(<a\b[^>]*\bdata-stars\b[^>]*>)(.*?)(</a>)', re.DOTALL)
VALUE = re.compile(r'(<span class="metric-value" data-value>)([^<]*)(</span>)')


def get_star_count(repo):
    environment = os.environ.copy()
    environment['GH_PROMPT_DISABLED'] = '1'
    environment['GIT_TERMINAL_PROMPT'] = '0'
    for attempt in range(3):
        try:
            result = subprocess.run(
                ['gh', 'api', f'repos/{repo}', '--jq', '.stargazers_count'],
                env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=25,
            )
        except FileNotFoundError:
            raise PublishError('GitHub CLI (gh) is not installed') from None
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            count = result.stdout.strip()
            if count.isascii() and count.isdigit() and int(count) <= 100_000_000:
                return int(count)
            raise PublishError(f'GitHub returned an invalid star count for {repo}')
        if attempt < 2:
            time.sleep(attempt + 1)
    raise PublishError(f'Could not read GitHub stars for {repo}; check the network and gh login')


def update_html(html, counts):
    papers = list(PAPER.finditer(html))
    if not papers or len(papers) != html.count('class="paper-metrics"'):
        raise PublishError('Could not identify every selected paper in the homepage')
    repos = [paper.group('repo') for paper in papers]
    if set(repos) != set(counts):
        raise PublishError('Star counts do not match the selected papers')

    def update_paper(paper):
        repo = paper.group('repo')
        block = paper.group(0)
        links = list(STAR_LINK.finditer(block))
        if len(links) != 1:
            raise PublishError(f'Expected one star link for {repo}')
        link = links[0]
        if len(VALUE.findall(link.group(2))) != 1:
            raise PublishError(f'Expected one star count for {repo}')
        new_body = VALUE.sub(lambda value: value.group(1) + format(counts[repo], ',') + value.group(3), link.group(2))
        new_link = link.group(1) + new_body + link.group(3)
        return block[:link.start()] + new_link + block[link.end():]

    return PAPER.sub(update_paper, html)


def main():
    remote = git(['remote', 'get-url', 'origin'], REPOSITORY, 'Reading the Git remote')
    if remote.removesuffix('.git').lower() not in ALLOWED_REMOTES:
        raise PublishError('The Git remote is not the expected homepage repository')
    author_name = git(['config', 'user.name'], REPOSITORY, 'Reading the Git author name')
    author_email = git(['config', 'user.email'], REPOSITORY, 'Reading the Git author email')

    with tempfile.TemporaryDirectory(prefix='homepage-stars-') as directory:
        temporary = Path(directory)
        clone = temporary / 'homepage'
        git(['clone', '--quiet', '--depth', '1', '--single-branch', '--branch', BRANCH,
             '--no-tags', '--', remote, str(clone)], temporary, 'Cloning the homepage')
        if git(['branch', '--show-current'], clone, 'Checking the homepage branch') != BRANCH:
            raise PublishError('The homepage branch is not checked out')
        path = clone / 'index.html'
        html = path.read_text(encoding='utf-8')
        papers = list(PAPER.finditer(html))
        if not papers or len(papers) != html.count('class="paper-metrics"'):
            raise PublishError('Could not identify every selected paper in the homepage')
        repos = list(dict.fromkeys(paper.group('repo') for paper in papers))
        counts = {repo: get_star_count(repo) for repo in repos}
        updated = update_html(html, counts)
        if updated == html:
            print('GitHub star counts are already up to date.')
            return
        path.write_text(updated, encoding='utf-8')
        git(['config', 'user.name', author_name], clone, 'Setting the Git author name')
        git(['config', 'user.email', author_email], clone, 'Setting the Git author email')
        git(['add', '--', 'index.html'], clone, 'Staging the homepage star counts')
        changed = git(['diff', '--cached', '--name-only'], clone, 'Checking staged changes')
        if changed != 'index.html':
            raise PublishError('Unexpected files were staged')
        git(['diff', '--cached', '--check'], clone, 'Checking the homepage star counts')
        git(['commit', '--quiet', '-m', 'Update GitHub star counts'], clone, 'Creating the star count commit')
        git(['push', 'origin', f'HEAD:refs/heads/{BRANCH}'], clone, 'Publishing the star counts')
        print('Updated GitHub stars: ' + ', '.join(f'{repo} {count}' for repo, count in counts.items()))


if __name__ == '__main__':
    try:
        main()
    except (PublishError, OSError, ValueError) as error:
        print(f'Star update failed: {error}', file=sys.stderr)
        raise SystemExit(1)
