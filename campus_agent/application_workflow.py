"""Prepare one role using the existing advert, evidence and document services."""
from __future__ import annotations

import base64
import hashlib
import re
import shutil
import time
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .career import TERMINAL
from .career_exports import _pdf
from .models import Job
from .scoring_comparison import compare, quoted_requirements
from .semantic import comparison_fingerprint
from .transfer_fit import score

FORMATS = {'zip', 'pdf', 'files'}
DELIVERY = {'download', 'email'}
MIME = {'.zip': 'application/zip', '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def criterion_key(row):
    return (' '.join(row['quote'].split()), row['importance'], row['kind'])


def carry_review(previous, requirements):
    """Keep a current review when rereading the advert only changed its presentation."""
    if not previous:
        return None
    old = {criterion_key(row): row for row in previous['requirements']}
    if len(old) != len(requirements) or old.keys() != {criterion_key(row) for row in requirements}:
        return None
    carried = []
    for requirement in requirements:
        prior = old[criterion_key(requirement)]
        carried.append({**requirement, 'status': prior['evidence_state'], 'evidence': prior['evidence'],
                        'transfer_reason': prior.get('transfer_reason', '')})
    return {**score(carried), 'reviewed': True, 'reviewed_by': previous['reviewed_by']}


class ApplicationWorkflow:
    def __init__(self, workspace):
        self.workspace = workspace
        self.directory = workspace.artifacts / 'application-workflows'

    def _key(self, job_id):
        return 'application_workflow:' + job_id

    def get(self, job_id):
        run = self.workspace.get_meta(self._key(job_id))
        if run:
            with self.workspace.store.connect() as db:
                for record in (run, run.get('mail') or {}):
                    if record.get('status') not in {'running', 'sending'} or not record.get('task_id'):
                        continue
                    task = db.execute('SELECT status FROM tasks WHERE id=?', (record['task_id'],)).fetchone()
                    if task and task[0] == 'interrupted':
                        record.update(status='failed' if record is run else 'needs_review',
                                      error='NextRole stopped during this operation. Check Activity before retrying.')
        return run

    def _update(self, job_id, run_id, **changes):
        with self.workspace.write_lock:
            run = self.workspace.get_meta(self._key(job_id))
            if not run or run['id'] != run_id:
                raise ValueError('This preparation run has been replaced.')
            run.update(changes)
            self.workspace.set_meta(self._key(job_id), run)
            return run

    def _row(self, job_id):
        row = next((row for row in self.workspace.jobs() if row['id'] == job_id), None)
        if row is None or row['source_policy'] or row['listing']['closed']:
            raise ValueError('Choose an open role from an allowed source.')
        if not self.workspace.profile or self.workspace.profile.is_example:
            raise ValueError('Save your confirmed profile before preparing documents.')
        return row

    def start(self, job_id, options):
        if (not isinstance(options, dict) or set(options) != {'format', 'delivery', 'deeper_fit'}
                or not isinstance(options['format'], str) or options['format'] not in FORMATS
                or not isinstance(options['delivery'], str) or options['delivery'] not in DELIVERY
                or type(options['deeper_fit']) is not bool):
            raise ValueError('Choose an output format, delivery option and fit check.')
        self._row(job_id)
        with self.workspace.write_lock:
            previous = self.get(job_id)
            if previous and (previous['status'] == 'running' or (previous.get('mail') or {}).get('status') == 'sending'):
                return previous
            account = self.workspace.get_meta('connections', {}).get('accounts', {}).get('gmail') or {}
            if options['delivery'] == 'email' and not (account.get('connected') and account.get('email') and account.get('id')):
                raise ValueError('Connect Gmail or choose Download before starting.')
            run = {'id': uuid.uuid4().hex, 'status': 'running', 'step': 'Rechecking the advert',
                   'options': options, 'files': [], 'warnings': [], 'mail': None}
            if options['delivery'] == 'email':
                run['account_id'] = account['id']
            self.workspace.set_meta(self._key(job_id), run)
            task = self.workspace.task('Prepare full application package', lambda: self._run(job_id, run['id'], options))
            return self._update(job_id, run['id'], **task)

    def _current(self, job_id, snapshot):
        profile = self.workspace.profile
        if not profile or comparison_fingerprint(self.workspace.job(job_id)[1], profile) != snapshot:
            raise ValueError('The advert or profile changed during preparation. Start a new run with the current details.')

    def _fit(self, job_id, row, profile, previous, snapshot, deeper):
        job = Job.model_validate(row['job'])
        result = compare(job, profile, quoted_requirements(row), with_qwen=deeper)
        with self.workspace.write_lock:
            self._current(job_id, snapshot)
            stored = self.workspace.get_meta('comparison:' + job_id) or {}
            current = stored.get('result', {}) if stored.get('fingerprint') == snapshot else {}
            reviewed = current.get('reviewed') or carry_review(previous, result['rules']['requirements'])
            if reviewed is not None:
                result['reviewed'] = reviewed
            if result['qwen'] is None:
                result['qwen'] = current.get('qwen')
            self.workspace.set_meta('comparison:' + job_id, {'fingerprint': snapshot, 'result': result})
        return result

    def _career(self, job_id, feature, directory):
        options = {}
        if feature == 'deep_research':
            previous = next((run for run in self.workspace.career.list(job_id)
                             if run['feature']==feature and run['status']=='ready_for_review'), None)
            if previous:
                options = {key:previous['options'][key] for key in
                           ('company_links','alternate_vacancy_url','technology_links') if key in previous['options']}
        run_id = self.workspace.career.start(job_id, feature, options)['run_id']
        deadline = time.monotonic() + 210
        while not self.workspace.stop_event.is_set() and time.monotonic() < deadline:
            run = self.workspace.career.get(run_id)
            if run['status'] in TERMINAL:
                if run['status'] != 'ready_for_review':
                    raise ValueError(run.get('error') or 'The document run did not complete.')
                paths = self.workspace.career.export_files(run_id, directory)
                return run, paths
            self.workspace.stop_event.wait(.75)
        raise ValueError('The document run has not finished. Check its progress in Next steps.')

    def _run(self, job_id, run_id, options):
        from .workspace import ReadInProgress, SourceChanged
        target = self.directory / run_id
        warnings = []
        files = []
        try:
            before = self._row(job_id)
            profile_before = self.workspace.profile.model_dump_json()
            prior = (before.get('evidence_comparison') or {}).get('reviewed')
            source = 'The saved advert was reread.'
            try:
                self.workspace.hydrate(job_id)
            except (ReadInProgress, SourceChanged):
                raise
            except Exception as error:
                if re.search(r'listing has expired|closing date of|describes another role', str(error), re.I):
                    raise ValueError(str(error)) from error
                source = 'Advert recheck could not be confirmed. Prepared from the saved advert.'
                warnings.append(source + ' ' + str(error)[:240])
            row = self._row(job_id)
            if not row['full_description'] or row['fit']['assessment_state'] in {'incomplete', 'needs_profile', 'excluded'}:
                raise ValueError('Read or paste the full advert before preparing documents.')
            profile = self.workspace.profile
            snapshot = comparison_fingerprint(Job.model_validate(row['job']), profile)
            if (profile.model_dump_json() != profile_before or
                    row['reading_view']['employer'] != before['reading_view']['employer'] or
                    row['reading_view']['title'] != before['reading_view']['title']):
                prior = None
            self._update(job_id, run_id, step='Checking fit against your profile', warnings=warnings)
            fit = None
            try:
                fit = self._fit(job_id, row, profile, prior, snapshot, options['deeper_fit'])
                if fit.get('qwen_error'):
                    warnings.append(fit['qwen_error'])
            except ValueError as error:
                warnings.append('Fit needs review: ' + str(error)[:240])
            fit_summary = self._fit_summary(fit)
            target.mkdir(parents=True, exist_ok=True)
            for feature, label in [('deep_research', 'Job research'), ('interview_prep', 'Interview prep')]:
                self._current(job_id, snapshot)
                self._update(job_id, run_id, step='Creating ' + label.lower(), warnings=warnings)
                try:
                    _, paths = self._career(job_id, feature, target / feature)
                except (OSError, ValueError) as error:
                    raise ValueError(label + ' needs attention before this package can be exported. ' + str(error)) from error
                for kind, path in paths.items():
                    part, suffix = kind.split('_')
                    name = f'{label} {"guide" if part == "guide" else "quick sheet"}.{suffix}'
                    destination = target / name
                    shutil.copyfile(path, destination)
                    files.append(destination)
            self._update(job_id, run_id, step='Creating résumé and cover letter', warnings=warnings)
            with self.workspace.write_lock:
                self._current(job_id, snapshot)
                try:
                    packet = self.workspace.prepare(job_id)
                    for name in ('Resume.pdf', 'Cover Letter.pdf'):
                        original = Path(packet['packet']) / name
                        expected = packet['quality']['files'][name]['sha256']
                        if not original.resolve().is_relative_to(self.workspace.artifacts) or file_hash(original) != expected:
                            raise ValueError('The prepared application file could not be verified.')
                        destination = target / name
                        shutil.copyfile(original, destination)
                        files.append(destination)
                except (ValueError, OSError) as error:
                    warnings.append('Application PDFs could not be exported: ' + str(error)[:240])
            self._current(job_id, snapshot)
            report = target / 'Preparation summary.pdf'
            details = ['## Advert and fit', source, fit_summary, '## What to review',
                       'The research guide passed source and coverage checks. Interview answers use your saved evidence. Review the résumé and cover letter before using them.']
            details += ['- ' + warning for warning in warnings]
            _pdf(report, row['reading_view']['title'] + ' — ' + row['reading_view']['employer'], '\n\n'.join(details), 'NextRole · Draft preparation package')
            files.insert(0, report)
            self._update(job_id, run_id, step='Exporting the package')
            selected = self._export(target, files, options['format'])
            self._current(job_id, snapshot)
            self._update(job_id, run_id, status='ready', step='Ready to review', warnings=warnings,
                         fit_summary=fit_summary, research_checked=True, files=[{'name': p.name, 'sha256': file_hash(p)} for p in selected])
            return {'job_id': job_id, 'file_count': len(selected)}
        except Exception as error:
            self._update(job_id, run_id, status='failed', step='Preparation stopped', error=str(error)[:450], warnings=warnings)
            raise

    @staticmethod
    def _fit_summary(result):
        if not result:
            return 'Fit needs review.'
        arm = result.get('reviewed') or result.get('qwen')
        if arm and arm['percent'] is not None:
            label = 'Reviewed fit' if result.get('reviewed') else 'Local Qwen suggestion'
            return f"{label}: {arm['percent']}% · {arm['evidence_coverage_percent']}% of criteria assessed. Provisional."
        return f"Fit needs review. Direct evidence covers {result['rules']['evidence_coverage_percent']}% of weighted criteria."

    @staticmethod
    def _export(target, files, output_format):
        if output_format == 'files':
            return files
        if output_format == 'zip':
            path = target / 'NextRole preparation.zip'
            with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
                for source in files:
                    archive.write(source, source.name)
            return [path]
        from pypdf import PdfWriter
        path = target / 'NextRole preparation.pdf'
        with PdfWriter() as writer:
            for source in files:
                if source.suffix == '.pdf':
                    writer.append(source)
            with path.open('wb') as output:
                writer.write(output)
        return [path]

    def file(self, job_id, run_id, name):
        run = self.get(job_id)
        if not run or run['id'] != run_id or run['status'] != 'ready':
            raise ValueError('This package is not available.')
        if not run.get('research_checked'):
            raise ValueError('Prepare the package again to run the updated research checks.')
        entry = next((entry for entry in run['files'] if entry['name'] == name), None)
        path = (self.directory / run_id / name).resolve()
        if not entry or not path.is_relative_to(self.directory.resolve()) or not path.is_file() or file_hash(path) != entry['sha256']:
            raise ValueError('The requested preparation file could not be verified.')
        return path

    def send(self, job_id, run_id):
        with self.workspace.write_lock:
            run = self.get(job_id)
            if not run or run['id'] != run_id or run['status'] != 'ready' or run['options']['delivery'] != 'email':
                raise ValueError('Select Email me before preparing a package.')
            if not run.get('research_checked'):
                raise ValueError('Prepare the package again to run the updated research checks.')
            if run.get('mail'):
                return run
            self._update(job_id, run_id, mail={'status': 'sending'})
            task = self.workspace.task('Email preparation package to your inbox', lambda: self._send(job_id, run_id, run))
            return self._update(job_id, run_id, mail={'status': 'sending', **task})

    def _send(self, job_id, run_id, run):
        receipt = {'status': 'needs_review'}
        try:
            account = self.workspace.require_account('gmail')
            if account.get('id') != run['account_id'] or not account.get('email'):
                raise ValueError('The connected Gmail account changed. Check the destination before sending.')
            parts = [{'mime_type': 'text/html', 'charset': 'utf-8', 'body': {'content': '<p>Your NextRole preparation files are attached for your review.</p>'}}]
            for entry in run['files']:
                path = self.file(job_id, run_id, entry['name'])
                parts.append({'mime_type': MIME[path.suffix], 'filename': path.name, 'content_disposition': 'attachment',
                              'body': {'base64_url_content': base64.urlsafe_b64encode(path.read_bytes()).decode()}})
            job = self.workspace.job(job_id)[1]
            subject = re.sub(r'[\r\n]+', ' ', 'NextRole preparation — ' + job.title)[:180]
            sent = self.workspace.bridge.call('gmail.send_email', {'to': account['email'], 'subject': subject,
                'payload': {'mime_type': 'multipart/mixed', 'parts': parts}, 'response_fields': ['id']})
            identity = sent.get('id') or (sent.get('message') or {}).get('id')
            if not identity:
                raise ValueError('Gmail did not return a message ID. Check Sent before retrying.')
            receipt['message_id'] = identity
            message = self.workspace.bridge.call('gmail.read_email', {'message_id': identity, 'format': 'full'})
            payload = message.get('message', message).get('payload', {})
            names = set()
            def collect(part):
                if part.get('filename'):
                    names.add(part['filename'])
                for child in part.get('parts') or []:
                    collect(child)
            collect(payload)
            if names != {entry['name'] for entry in run['files']}:
                raise ValueError('Gmail accepted the message but its attachments need confirmation in Sent.')
            receipt.update(status='sent', attachment_count=len(names))
            self._update(job_id, run_id, mail=receipt)
            return receipt
        except Exception as error:
            self._update(job_id, run_id, mail={**receipt, 'error': str(error)[:450]})
            raise
