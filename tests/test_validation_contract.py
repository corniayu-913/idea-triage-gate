"""Regression cases for the six externally reproduced validation gaps."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/validate_assessment.py'
spec = importlib.util.spec_from_file_location('contract_validator', SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((ROOT / 'examples/assessment-v2.json').read_text())

    def source(self):
        return dict(source_id='S001', canonical_work_id='test:one', title='Synthetic source',
                    authors_or_organization=None, venue_or_source=None, publication_date=None,
                    url_or_doi=None, version=None, accessed_at='2026-10-12T00:00:00+01:00',
                    inspected_scope='Synthetic test', read_status='audited', relevant_claim=None,
                    evidence_note=None, limitations=None, reviewer='test', reused_from=None)

    def with_source(self):
        self.report['evidence_summary'].update(audited=1, fully_read=0, newly_inspected=1, reused=0)
        self.report['venues'] = [dict(name='Synthetic venue', track=None, fit='Synthetic scope',
                                      positioning='plausible target', requirements=['Verify claim'], source_ids=['S001'])]
        return [self.source()]

    def errors(self, ledger=None):
        return validator.validate_report(self.report, evidence_records=ledger)

    def reject(self, text, ledger=None):
        self.assertTrue(any(text in error for error in self.errors(ledger)), self.errors(ledger))

    def test_confirmation_reference_missing_or_blank(self):
        for value in [None, '', '  ', [], False]:
            with self.subTest(value=value):
                self.report['confirmation']['evidence_reference'] = value
                self.reject('confirmation.evidence_reference')
        del self.report['confirmation']['evidence_reference']
        self.reject('missing confirmation.evidence_reference')

    def test_each_academic_explanation_required_for_score(self):
        original = copy.deepcopy(self.report)
        for field in ('rationale', 'novelty_delta', 'significance', 'contribution_depth'):
            for value in (None, '', ' ', [], 5):
                with self.subTest(field=field, value=value):
                    self.report = copy.deepcopy(original)
                    self.report['academic'][field] = value
                    self.reject('academic.' + field)
            self.report = copy.deepcopy(original)
            del self.report['academic'][field]
            self.reject('missing academic.' + field)

    def test_awaiting_confirmation_can_remain_unscored(self):
        for key in self.report['academic']:
            self.report['academic'][key] = None
        self.report['confirmation'].update(status='awaiting', evidence_reference=None)
        self.report['policy']['minimum_score'] = None
        self.report['gate'].update(verdict=None, status='awaiting_policy', criteria_checks=[])
        self.assertEqual(self.errors(), [])

    def test_valid_ledger_and_citation(self):
        self.assertEqual(self.errors(self.with_source()), [])

    def test_unknown_venue_source(self):
        ledger = self.with_source()
        self.report['venues'][0]['source_ids'] = ['S999']
        self.reject('unknown venue source_id S999', ledger)

    def test_ledger_required_in_function_api(self):
        self.with_source()
        self.reject('evidence ledger required')

    def test_nonzero_counts_require_ledger_even_without_venues(self):
        self.report['evidence_summary']['audited'] = 1
        self.reject('evidence ledger required')

    def test_duplicate_source_ids_and_work_families(self):
        ledger = self.with_source()
        ledger.append(copy.deepcopy(ledger[0]))
        self.reject('duplicate source_id', ledger)
        ledger[1]['source_id'] = 'S002'
        self.reject('duplicate canonical_work_id', ledger)

    def test_counts_cannot_be_negative_boolean_or_fractional(self):
        for key in ('audited', 'fully_read', 'newly_inspected', 'reused'):
            for value in (-1, True, 1.5, '2', None):
                with self.subTest(key=key, value=value):
                    r = copy.deepcopy(self.report)
                    r['evidence_summary'][key] = value
                    self.assertTrue(any('evidence_summary.' + key in e for e in validator.validate_report(r)))

    def test_full_reads_cannot_exceed_audits(self):
        self.report['evidence_summary'].update(audited=0, fully_read=15)
        self.reject('fully_read cannot exceed audited')

    def test_totals_must_match_ledger(self):
        ledger = self.with_source()
        for key in ('audited', 'fully_read', 'newly_inspected', 'reused'):
            saved = self.report['evidence_summary'][key]
            self.report['evidence_summary'][key] = saved + 1
            self.reject('evidence_summary.' + key + ' disagrees', ledger)
            self.report['evidence_summary'][key] = saved

    def test_full_read_counts_as_audit(self):
        ledger = self.with_source()
        ledger[0]['read_status'] = 'full'
        self.report['evidence_summary']['fully_read'] = 1
        self.assertEqual(self.errors(ledger), [])

    def test_reused_and_reinspected_sources(self):
        ledger = self.with_source()
        ledger[0]['reused_from'] = '../r001/evidence.jsonl'
        self.report['evidence_summary'].update(newly_inspected=0, reused=1)
        self.assertEqual(self.errors(ledger), [])
        ledger[0]['inspected_in_run'] = True
        self.report['evidence_summary'].update(newly_inspected=1, reused=0)
        self.assertEqual(self.errors(ledger), [])
        ledger[0]['inspected_in_run'] = 'yes'
        self.reject('inspected_in_run', ledger)

    def test_invalid_timestamp_and_identifiers(self):
        for key, values in {
            'assessed_at': ['not-a-date', '2026-02-30T12:00:00Z', '2026-10-12T00:00:00', None, 42],
            'idea_revision': ['banana', 'i000', 'i1', None],
            'run_id': ['r000', 'r1', {}, 'i001'],
            'idea_id': ['banana', '2026-02-30--idea--1234abcd', '2026-10-12--idea--nope', None],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    r = copy.deepcopy(self.report); r[key] = value
                    self.assertTrue(any(key in e for e in validator.validate_report(r)))

    def test_valid_real_identifier_timezone_and_large_sequence(self):
        self.report.update(idea_id='2026-10-12--inventory-test--12ab34cd', idea_revision='i1000', run_id='r1000', assessed_at='2026-10-12T00:00:00.123Z')
        self.assertEqual(self.errors(), [])

    def test_synthetic_id_requires_explicit_boolean(self):
        self.report['evidence_summary']['synthetic'] = 'true'
        self.reject('idea_id')

    def test_preferred_venues_must_be_string_array(self):
        for value in ['not-an-array', None, [None], [''], [' '], [True], [{}]]:
            with self.subTest(value=value):
                self.report['policy']['preferred_venues'] = value
                self.reject('policy.preferred_venues')

    def test_venue_fields_and_types(self):
        ledger = self.with_source()
        original = copy.deepcopy(self.report['venues'][0])
        for key in original:
            self.report['venues'][0] = copy.deepcopy(original)
            del self.report['venues'][0][key]
            self.reject('missing venues[0].' + key, ledger)
        self.report['venues'][0] = original
        self.report['venues'][0]['source_ids'] = [['S001']]
        self.reject('source_ids', ledger)

    def test_malformed_json_shapes_do_not_crash(self):
        for key in ('academic', 'policy', 'gate', 'confirmation', 'evidence_summary', 'venues'):
            for value in (None, [], 1, 'x'):
                if key == 'venues' and value == []:
                    continue  # The shipped zero-source synthetic fixture has no venues.
                with self.subTest(key=key, value=value):
                    r = copy.deepcopy(self.report); r[key] = value
                    self.assertTrue(validator.validate_report(r))
        for ledger in ({}, 'x', [None], [[]], [{'source_id': [], 'canonical_work_id': {}}]):
            self.assertTrue(self.errors(ledger))

    def test_source_record_required_fields_and_metadata(self):
        ledger = self.with_source()
        del ledger[0]['title']
        self.reject('missing evidence[0].title', ledger)
        ledger[0]['accessed_at'] = 'yesterday'
        self.reject('accessed_at', ledger)
        ledger[0]['read_status'] = 'downloaded'
        self.reject('read_status', ledger)

    def test_reserved_criterion_is_rejected(self):
        self.report['policy']['mandatory_venue_criteria'] = ['minimum_score']
        self.reject('reserved')

    def run_cli(self, result, *options):
        return subprocess.run([sys.executable, str(SCRIPT), str(result), *map(str, options)], capture_output=True, text=True)

    def test_cli_loads_sibling_ledger_and_explicit_ledger(self):
        ledger = self.with_source()
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / 'result.json'; result.write_text(json.dumps(self.report))
            path = Path(tmp) / 'evidence.jsonl'; path.write_text(json.dumps(ledger[0]) + '\n')
            self.assertEqual(self.run_cli(result).returncode, 0)
            other = path.with_name('other.jsonl'); path.rename(other)
            self.assertEqual(self.run_cli(result, '--evidence', other).returncode, 0)
            self.assertEqual(self.run_cli(result).returncode, 1)

    def test_cli_reports_malformed_missing_and_invalid_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / 'result.json'; result.write_text(json.dumps(self.report))
            path = Path(tmp) / 'evidence.jsonl'; path.write_text('broken\n')
            bad = self.run_cli(result)
            self.assertEqual(bad.returncode, 1)
            self.assertIn(':1: invalid JSON', bad.stderr)
            self.assertNotIn('Traceback', bad.stderr)
            path.unlink()
            self.assertEqual(self.run_cli(result, '--evidence', path).returncode, 1)
            path.write_text('[]\n')
            self.assertEqual(self.run_cli(result).returncode, 1)


if __name__ == '__main__':
    unittest.main()
