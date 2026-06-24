"""
Session report writer.
Appends a Markdown block to ~/cad2urdf_report.md after every pipeline run.
"""
import os
from datetime import datetime
from typing import List, Tuple, Optional

REPORT_PATH = os.path.join(os.path.expanduser('~'), 'cad2urdf_report.md')
_ICONS = {'ok': 'OK', 'warn': 'WARN', 'fail': 'FAIL', 'skip': 'SKIP'}


class SessionLog:
    """Collect pipeline events, then flush to the markdown report."""

    def __init__(self, session_type: str = 'Analysis'):
        self._type    = session_type
        self._start   = datetime.now()
        self._file: Optional[str] = None
        self._steps:  List[Tuple[str, str, str]] = []
        self._warns:  List[str] = []
        self._error:  Optional[str] = None

    def set_file(self, path: str):
        self._file = path

    def step(self, name: str, status: str, notes: str = ''):
        """status in 'ok' | 'warn' | 'fail' | 'skip'"""
        tag = _ICONS.get(status.lower(), status.upper())
        self._steps.append((name, tag, notes))

    def warning(self, msg: str):
        self._warns.append(msg)

    def error(self, msg: str):
        self._error = msg

    def write(self):
        """Append this session block to REPORT_PATH. Never raises."""
        try:
            self._flush()
        except Exception:
            pass

    def _flush(self):
        dur = (datetime.now() - self._start).total_seconds()
        ts  = self._start.strftime('%Y-%m-%d %H:%M:%S')

        lines = ['', '---', f'## {self._type} -- {ts}', '']

        if self._file:
            lines += [
                '### File',
                f'- Path: {self._file}',
                f'- Duration: {dur:.1f} s',
                '',
            ]

        if self._steps:
            lines += [
                '### Pipeline Steps',
                '',
                '| Step | Status | Notes |',
                '|------|--------|-------|',
            ]
            for name, tag, notes in self._steps:
                safe = notes.replace('|', '/').replace('\n', ' ')
                lines.append(f'| {name} | {tag} | {safe} |')
            lines.append('')

        if self._warns:
            lines += [f'### Warnings ({len(self._warns)})', '']
            for i, w in enumerate(self._warns, 1):
                lines.append(f'{i}. {w}')
            lines.append('')

        if self._error:
            cap = self._error[:3000]
            lines += ['### ERROR', '', '```', cap, '```', '']
        else:
            lines += ['### Result: completed successfully', '']

        block = '\n'.join(lines) + '\n'
        new   = not os.path.isfile(REPORT_PATH)
        with open(REPORT_PATH, 'a', encoding='utf-8') as fh:
            if new:
                fh.write('# CAD2URDF Session Report\n\n')
                fh.write('One block per run, newest at the bottom.\n')
                fh.write(f'Location: {REPORT_PATH}\n')
            fh.write(block)
