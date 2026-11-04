#!/usr/bin/env python3
"""Fetch Google Scholar citations locally and publish the data-only branch."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = Path(__file__).resolve().parent.parent
BRANCH = 'scholar-metrics'
ALLOWED_REMOTES = {
    'git@github.com:chuan-10/chuan-10.github.io',
    'https://github.com/chuan-10/chuan-10.github.io',
    'ssh://git@github.com/chuan-10/chuan-10.github.io',
}


class PublishError(Exception):
    pass


def git(args, cwd, label):
    environment = os.environ.copy()
    environment['GIT_TERMINAL_PROMPT'] = '0'
    try:
        result = subprocess.run(
            ['git', *args], cwd=cwd, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PublishError(f'{label} could not be completed') from None
    if result.returncode:
        raise PublishError(f'{label} failed (exit {result.returncode})')
    return result.stdout.strip()


def refresh_snapshot(target):
    try:
        result = subprocess.run(
            [sys.executable, str(REPOSITORY / 'scripts/update_scholar.py'), str(target)],
            cwd=REPOSITORY, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PublishError('Google Scholar could not be reached') from None
    if result.returncode:
        message = result.stderr.strip()
        if message.startswith('Citation update failed:'):
            raise PublishError(message)
        raise PublishError('Google Scholar citation update failed')


def main():
    remote = git(['remote', 'get-url', 'origin'], REPOSITORY, 'Reading the Git remote')
    normalized = remote.removesuffix('.git').lower()
    if normalized not in ALLOWED_REMOTES:
        raise PublishError('The Git remote is not the expected homepage repository')
    author_name = git(['config', 'user.name'], REPOSITORY, 'Reading the Git author name')
    author_email = git(['config', 'user.email'], REPOSITORY, 'Reading the Git author email')

    with tempfile.TemporaryDirectory(prefix='scholar-citations-') as directory:
        temporary = Path(directory)
        snapshot = temporary / 'citation-counts.json'
        refresh_snapshot(snapshot)
        data = json.loads(snapshot.read_text(encoding='utf-8'))
        clone = temporary / 'data-branch'
        git(['clone', '--quiet', '--single-branch', '--branch', BRANCH, '--no-tags', '--', remote, str(clone)],
            temporary, 'Cloning the citation branch')
        if git(['branch', '--show-current'], clone, 'Checking the citation branch') != BRANCH:
            raise PublishError('The citation branch is not checked out')
        git(['config', 'user.name', author_name], clone, 'Setting the Git author name')
        git(['config', 'user.email', author_email], clone, 'Setting the Git author email')
        shutil.copyfile(snapshot, clone / 'citation-counts.json')
        git(['add', '--', 'citation-counts.json'], clone, 'Staging the citation snapshot')
        changed = git(['diff', '--cached', '--name-only'], clone, 'Checking staged changes')
        if changed and changed != 'citation-counts.json':
            raise PublishError('Unexpected files were staged')
        if changed:
            git(['diff', '--cached', '--check'], clone, 'Checking the citation snapshot')
            git(['commit', '--quiet', '-m', 'Update Google Scholar citations'], clone, 'Creating the snapshot commit')
            git(['push', 'origin', f'HEAD:refs/heads/{BRANCH}'], clone, 'Publishing the citation snapshot')
        print(f"Google Scholar snapshot updated: {data['updated_at']}")


if __name__ == '__main__':
    try:
        main()
    except (PublishError, OSError, ValueError, KeyError) as error:
        print(f'Citation publish failed: {error}', file=sys.stderr)
        raise SystemExit(1)
