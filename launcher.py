"""First-run installer and local launcher. Standard library only; macOS release."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent


def environment():
    env = os.environ.copy()
    extra = [str(Path.home() / '.local/bin'), '/opt/homebrew/bin', '/usr/local/bin']
    env['PATH'] = os.pathsep.join(extra + [env.get('PATH', '')])
    return env


def python_path():
    return ROOT / '.venv/bin/python'


def dependency_probe(python):
    """Check all pinned versions and app imports without contacting an account."""
    if not python.is_file():
        return False
    code = '''import importlib.metadata as m, pathlib, sys
assert sys.version_info >= (3,12)
for line in pathlib.Path("requirements-lock.txt").read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        name, version = line.split("==", 1)
        assert m.version(name) == version, name
import campus_agent.workspace_web, campus_agent.morning
'''
    result = subprocess.run([str(python), '-c', code], cwd=ROOT, env=environment(),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def install_dependencies():
    python = python_path()
    if not python.is_file():
        print('First launch: creating a private Python environment in .venv ...', flush=True)
        venv.create(ROOT / '.venv', with_pip=True)
    if not dependency_probe(python):
        print('Installing the pinned dependencies. First run needs internet; please wait.\n', flush=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements-lock.txt')],
                       cwd=ROOT, env=environment(), check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '-e', str(ROOT)],
                       cwd=ROOT, env=environment(), check=True)
        if not dependency_probe(python):
            raise RuntimeError('Dependency check failed. Keep the error above and see START HERE.html.')
    return python


def existing_workspace(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/state', timeout=2) as response:
            state = json.load(response)
        return state.get('kind') == 'job-workspace' and state.get('path') == str((ROOT / 'workspace').resolve())
    except (OSError, ValueError):
        return False


def serve(python, port, open_browser=True):
    url = f'http://127.0.0.1:{port}/'
    if existing_workspace(port):
        print(f'Your NextRole is already running: {url}')
        if open_browser:
            webbrowser.open(url)
        return
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError as exc:
            raise RuntimeError(f'Port {port} is in use by another app or another copy of NextRole. '
                               'Close that copy, or see the port instructions in the guide.') from exc
    print(f'\nNextRole: {url}\nKeep this Terminal window open. Press Control+C to stop.\n', flush=True)
    process = subprocess.Popen([str(python), '-m', 'campus_agent', 'workspace',
                                '--directory', str(ROOT / 'workspace'), '--port', str(port)],
                               cwd=ROOT, env=environment())
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('NextRole stopped before starting. Check the error above.')
            if existing_workspace(port):
                if open_browser:
                    webbrowser.open(url)
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Startup took too long. Check the error above before trying again.')
        process.wait()
        if process.returncode:
            raise RuntimeError(f'NextRole stopped (exit {process.returncode}). Check the error above.')
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description='Install dependencies and open NextRole on this Mac')
    parser.add_argument('--check', action='store_true', help='Show local setup status only; no install or account access')
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError('Install Python 3.12 or later from https://www.python.org/downloads/macos/ first.')
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    codex = shutil.which('codex', path=environment()['PATH'])
    if args.check:
        print(f'Python: {sys.version.split()[0]}\nFolder: {ROOT}')
        print('Python dependencies: ' + ('ready' if dependency_probe(python_path()) else 'will install on first launch'))
        print('Codex CLI: ' + ('found (account access not checked)' if codex else 'not found; follow START HERE.html'))
        print('This check does not sign in, search jobs, send mail or install schedules.')
        return
    python = install_dependencies()
    if not codex:
        print('\nCodex CLI is not installed or not on PATH. Local profile editing and pasted jobs still work.\n'
              'For connected search, Gmail and Drive, follow START HERE.html and relaunch.\n', flush=True)
    serve(python, args.port, not args.no_browser)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nNextRole stopped. Your saved workspace is kept.')
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'\nSetup stopped: {error}\nSee START HERE.html for help.', file=sys.stderr)
        sys.exit(1)
