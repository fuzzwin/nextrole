"""Build a clean Mac source ZIP from an explicit allowlist, never a used folder."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_guide import build as build_guide

FILES = (
    'LICENSE',
    'assets/nextrole-banner.png', 'assets/nextrole-workspace.jpg', 'assets/README.md',
    'README.md', 'setup/START HERE.txt', 'setup/START HERE.html', 'setup/CODEX SETUP PROMPT.txt', 'setup/Start Job Seeker.command',
    'Start NextRole.command', 'CHANGELOG.md', 'PRIVACY.md', 'launcher.py', 'pyproject.toml', 'requirements-lock.txt', '.gitignore', '.env.example',
    'config.example.json', 'profile.example.json', 'examples/jobs.json', 'setup/Start-Demo.command',
    'docs/USER-GUIDE.md', 'docs/ROLE-TAILORING.md', 'docs/LEGACY-CLI.md', 'scripts/build_release.py', 'scripts/build_guide.py',
)
MODULES = (
    '__init__.py', '__main__.py', 'application_review.py', 'applications.py', 'cli.py', 'connectors.py',
    'dashboard.html', 'document_style.py', 'documents.py', 'fit.py', 'listing_info.py', 'listing_view.py',
    'locations.py', 'mail.py', 'mcp_server.py', 'models.py', 'morning.py', 'packet_checks.py',
    'pipeline.py', 'role_types.py', 'sources.py', 'store.py', 'tailor.py', 'web.py',
    'workspace.html', 'workspace.py', 'workspace_web.py',
)
RELEASE_FILES = FILES + tuple('campus_agent/' + name for name in MODULES)
BLOCKED_PARTS = {'workspace', 'data', 'artifacts', 'output', 'tmp', 'evidence', '.venv',
                 '.git', '__pycache__', '.pytest_cache', 'dist', 'demo'}
SECRET_PATTERNS = (
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',
    r'\bya29\.[A-Za-z0-9_-]{20,}',
    '/' + 'Users' + r'/[^/\s]+/',
)
# Binary assets must be visually reviewed and pinned before they can be shared.
# Only reviewed synthetic-data captures may be included; no private-workspace screenshots.
BINARY_SHA256 = {
    'assets/nextrole-workspace.jpg': '9cfda945c853d4567bd644a1c81765397cf5df22c63583ac1cc63b20c7275872',
    'assets/nextrole-banner.png': '038eb6f8faa0fe026b3c9695e7b18a4045a23b4eaad3671fc01f9afff296563a',
}


def audit(relative, content, private_patterns=()):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or set(path.parts) & BLOCKED_PARTS:
        raise ValueError(f'Private/runtime path refused: {relative}')
    if relative not in RELEASE_FILES:
        raise ValueError(f'File is not on the release allowlist: {relative}')
    if relative in BINARY_SHA256:
        if hashlib.sha256(content).hexdigest() != BINARY_SHA256[relative]:
            raise ValueError(f'Unreviewed binary asset refused: {relative}')
        return
    text = content.decode('utf-8')
    for pattern in (*SECRET_PATTERNS, *private_patterns):
        if re.search(pattern, text, re.I):
            raise ValueError(f'Privacy scan failed for {relative}; inspect locally before sharing')


def build(root=ROOT, output=None, private_patterns=()):
    root = root.resolve()
    output = (output or root / 'dist').resolve()
    # Check generated-guide paths before reading or writing them, too.
    for relative in RELEASE_FILES:
        path = root / relative
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)):
            raise ValueError(f'Symlink refused: {relative}')
    build_guide(root)
    version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    name = 'NextRole-Mac-' + version
    entries = []
    # Validate everything before creating a ZIP. No runtime directory is inspected.
    for relative in RELEASE_FILES:
        path = root / relative
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)):
            raise ValueError(f'Symlink refused: {relative}')
        content = path.read_bytes()
        audit(relative, content, private_patterns)
        entries.append((relative, content, 0o755 if relative.endswith('.command') else 0o644))
    output.mkdir(parents=True, exist_ok=True)
    target = output / (name + '.zip')
    manifest = {'version': version, 'platform': 'macOS', 'files': [
        {'path': relative, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
         'mode': oct(mode)} for relative, content, mode in entries]}
    manifest_content = json.dumps(manifest, indent=2).encode()
    temporary = target.with_suffix('.zip.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for relative, content, mode in (*entries, ('RELEASE-MANIFEST.json', manifest_content, 0o644)):
                info = zipfile.ZipInfo(name + '/' + relative)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise ValueError('ZIP integrity check failed')
            expected = {name + '/' + relative for relative, _, _ in entries} | {name + '/RELEASE-MANIFEST.json'}
            if set(archive.namelist()) != expected:
                raise ValueError('ZIP file list differs from audited allowlist')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    (output / (name + '.manifest.json')).write_bytes(manifest_content)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / (name + '.zip.sha256')).write_text(digest + '  ' + target.name + '\n')
    return target, manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--private-pattern', action='append', default=[], help='Additional private-data regex; never saved in manifest')
    args = parser.parse_args()
    archive, manifest = build(output=args.output, private_patterns=args.private_pattern)
    print(json.dumps({'archive': str(archive), 'source_files': len(manifest['files']),
                      'private_workspace_included': False}, indent=2))
