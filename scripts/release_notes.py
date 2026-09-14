"""Validate a release tag against source version and extract its changelog."""
import argparse
from pathlib import Path
import re


def release_notes(tag):
    source = Path('klmp3.py').read_text(encoding='utf-8')
    version = re.search(r'^APP_VERSION = "([^"]+)"$', source, re.M)[1]
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag) or tag != f'v{version}':
        raise ValueError(f'Tag {tag!r} must match APP_VERSION: v{version}')
    changelog = Path('Changelog.md').read_text(encoding='utf-8')
    match = re.search(r'^\[' + re.escape(version) + r'\][^\n]*\n(.*?)(?=^---\s*$|\Z)', changelog, re.M | re.S)
    if not match or not match[1].strip():
        raise ValueError(f'Missing changelog for {version}')
    return match[1].strip() + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    parser.add_argument('--output', default='release-notes.md')
    args = parser.parse_args()
    Path(args.output).write_text(release_notes(args.tag), encoding='utf-8')
