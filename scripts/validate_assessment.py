"""Validate v2 structure and the recorded academic screen, not scholarly truth."""
import argparse
from datetime import date, datetime
import json
import re
import sys
from pathlib import Path


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def string_array(value):
    return isinstance(value, list) and all(nonempty(x) for x in value)


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value
    ):
        return False
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is not None
    except ValueError:
        return False


def numbered_id(value, prefix):
    return (isinstance(value, str) and
            re.fullmatch(prefix + r'[0-9]{3,}', value) is not None and
            any(c != '0' for c in value[1:]))


def validate_report(r, evidence_records=None):
    """Validate the record plus an optional parsed evidence.jsonl ledger.

    A nonzero source count or any venue citation requires the ledger. This
    function never follows references or fetches sources. Nonempty confirmation
    provenance is structural evidence, not proof of actual user consent.
    """
    errors = []
    if not isinstance(r, dict):
        return ['report must be an object']
    required = {'schema_version', 'idea_id', 'idea_revision', 'run_id', 'prompt_version', 'assessed_at', 'confirmation', 'academic', 'policy', 'gate', 'venues', 'research_obligations', 'decisive_unknowns', 'evidence_summary', 'prior_run_reference'}
    errors.extend(f'missing {k}' for k in sorted(required - r.keys()))
    if r.get('schema_version') != '2.0':
        errors.append('schema_version must be 2.0')
    def obj(key):
        v = r.get(key)
        if not isinstance(v, dict):
            errors.append(f'{key} must be an object')
            return {}
        return v
    a, p, g, c = (obj(k) for k in ('academic', 'policy', 'gate', 'confirmation'))
    e = obj('evidence_summary')
    for name, value, fields in (
        ('academic', a, ('score', 'confidence', 'rationale', 'novelty_delta', 'significance', 'contribution_depth')),
        ('confirmation', c, ('status', 'evidence_reference')),
        ('policy', p, ('minimum_score', 'mandatory_venue_criteria', 'preferred_venues', 'user_instruction_reference')),
        ('gate', g, ('verdict', 'status', 'criteria_checks', 'rationale')),
    ):
        errors.extend(f'missing {name}.{key}' for key in fields if key not in value)
    if not timestamp(r.get('assessed_at')):
        errors.append('assessed_at must be an ISO-8601 timestamp with timezone')
    for key, prefix in (('idea_revision', 'i'), ('run_id', 'r')):
        if not numbered_id(r.get(key), prefix):
            errors.append(f'{key} must be {prefix} followed by at least 3 digits, with a positive sequence number')
    idea_id = r.get('idea_id')
    valid_idea_id = False
    if isinstance(idea_id, str):
        match = re.fullmatch(r'(\d{4}-\d{2}-\d{2})--[a-z0-9]+(?:-[a-z0-9]+)*--[0-9a-f]{8}', idea_id)
        if match:
            try:
                date.fromisoformat(match.group(1)); valid_idea_id = True
            except ValueError:
                pass
        # Preserve the shipped, explicitly labelled synthetic fixture.
        if e.get('synthetic') is True and re.fullmatch(r'synthetic-[a-z0-9]+(?:-[a-z0-9]+)*', idea_id):
            valid_idea_id = True
    if not valid_idea_id:
        errors.append('idea_id must follow the dated slug/hash contract (or synthetic-* for an explicit synthetic fixture)')
    if not nonempty(r.get('prompt_version')):
        errors.append('prompt_version must be a nonempty string')
    if r.get('prior_run_reference') is not None and not nonempty(r['prior_run_reference']):
        errors.append('prior_run_reference must be null or a nonempty string')
    for k in ('venues', 'research_obligations', 'decisive_unknowns'):
        if not isinstance(r.get(k), list):
            errors.append(f'{k} must be an array')
    score = a.get('score')
    valid_score = type(score) is int and 1 <= score <= 10
    if score is not None and not valid_score:
        errors.append('score must be an integer 1–10 or null')
    if a.get('confidence') not in ('low', 'medium', 'high', None):
        errors.append('invalid confidence')
    if valid_score and a.get('confidence') is None:
        errors.append('scored assessments need confidence')
    for key in ('rationale', 'novelty_delta', 'significance', 'contribution_depth'):
        value = a.get(key)
        if not nonempty(value) and (score is not None or value is not None):
            errors.append(f'academic.{key} must be nonempty for a scored assessment, or null when unknown')
    if c.get('status') not in ('confirmed', 'waived', 'awaiting'):
        errors.append('invalid confirmation status')
    if (score is not None or g.get('verdict') is not None) and c.get('status') not in ('confirmed', 'waived'):
        errors.append('scoring requires confirmation or waiver')
    ref = c.get('evidence_reference')
    if c.get('status') in ('confirmed', 'waived'):
        if not nonempty(ref):
            errors.append('confirmation.evidence_reference must be nonempty for confirmation or waiver')
    elif ref is not None and not nonempty(ref):
        errors.append('confirmation.evidence_reference must be null or a nonempty string')
    if not string_array(p.get('preferred_venues')):
        errors.append('policy.preferred_venues must be an array of nonempty strings')
    if not nonempty(p.get('user_instruction_reference')):
        errors.append('policy.user_instruction_reference must be nonempty')
    if not nonempty(g.get('rationale')):
        errors.append('gate.rationale must be nonempty')
    for key in ('research_obligations', 'decisive_unknowns'):
        if not string_array(r.get(key)):
            errors.append(f'{key} must be an array of nonempty strings')
    threshold = p.get('minimum_score')
    valid_threshold = type(threshold) is int and 1 <= threshold <= 10
    if threshold is not None and not valid_threshold:
        errors.append('minimum_score must be an integer 1–10 or null')
    mandatory = p.get('mandatory_venue_criteria', [])
    checks = g.get('criteria_checks', [])
    if not string_array(mandatory):
        errors.append('mandatory criteria must be nonempty strings in an array')
        mandatory = []
    if len(set(mandatory)) != len(mandatory):
        errors.append('duplicate mandatory criteria')
    if 'minimum_score' in mandatory:
        errors.append('minimum_score is reserved for the numeric threshold, not a mandatory venue criterion')
    if not isinstance(checks, list):
        errors.append('criteria_checks must be an array')
        checks = []
    expected = list(mandatory) + (['minimum_score'] if threshold is not None else [])
    statuses = {}
    for check in checks:
        if not isinstance(check, dict):
            errors.append('each check must be an object'); continue
        key, status = check.get('criterion'), check.get('status')
        if not isinstance(key, str):
            errors.append('criterion must be a string'); continue
        if key in statuses:
            errors.append('duplicate criterion check')
        statuses[key] = status
        if status not in ('met', 'not_met', 'unknown'):
            errors.append('invalid criterion status')
        if not isinstance(check.get('reason'), str) or not check['reason'].strip():
            errors.append('criterion check needs a reason')
    if set(statuses) != set(expected):
        errors.append('checks must match binding criteria exactly; preferences are nonbinding')
    if valid_threshold:
        actual = ('met' if score >= threshold else 'not_met') if valid_score else 'unknown'
        if statuses.get('minimum_score') != actual:
            errors.append('minimum_score check disagrees with score')
        statuses['minimum_score'] = actual
    if not expected:
        verdict, status = None, 'awaiting_policy'
    elif 'not_met' in statuses.values():
        verdict, status = 'NO-GO', 'decided'
    elif all(statuses.get(k) == 'met' for k in expected):
        verdict, status = 'GO', 'decided'
    else:
        verdict, status = None, 'incomplete'
    if (g.get('verdict'), g.get('status')) != (verdict, status):
        errors.append(f'gate must be {verdict!r} with status {status}')

    # Counts are totals over the unique registered ledger, not search hits.
    counts = {}
    for key in ('audited', 'fully_read', 'newly_inspected', 'reused'):
        if key not in e and key in ('newly_inspected', 'reused'):
            continue
        value = e.get(key)
        if type(value) is not int or value < 0:
            errors.append(f'evidence_summary.{key} must be a nonnegative integer')
        else:
            counts[key] = value
    if 'audited' in counts and 'fully_read' in counts and counts['fully_read'] > counts['audited']:
        errors.append('fully_read cannot exceed audited')

    citations = []
    venues = r.get('venues')
    if isinstance(venues, list):
        for i, venue in enumerate(venues):
            path = f'venues[{i}]'
            if not isinstance(venue, dict):
                errors.append(f'{path} must be an object'); continue
            for key in ('name', 'track', 'fit', 'positioning', 'requirements', 'source_ids'):
                if key not in venue:
                    errors.append(f'missing {path}.{key}')
            for key in ('name', 'fit'):
                if not nonempty(venue.get(key)):
                    errors.append(f'{path}.{key} must be nonempty')
            if venue.get('track') is not None and not nonempty(venue['track']):
                errors.append(f'{path}.track must be null or a nonempty string')
            if venue.get('positioning') not in ('stretch', 'plausible target', 'more conservative target'):
                errors.append(f'{path}.positioning is invalid')
            if not string_array(venue.get('requirements')):
                errors.append(f'{path}.requirements must be an array of nonempty strings')
            refs = venue.get('source_ids')
            if not string_array(refs):
                errors.append(f'{path}.source_ids must be an array of nonempty strings')
            else:
                if len(refs) != len(set(refs)):
                    errors.append(f'{path}.source_ids contains duplicates')
                citations.extend(refs)

    if evidence_records is None:
        if citations or any(counts.values()):
            errors.append('evidence ledger required for cited venues or nonzero evidence counts')
    elif not isinstance(evidence_records, list):
        errors.append('evidence ledger must be an array of source records')
    else:
        source_ids, works = set(), set()
        full = reused = 0
        required_source = {'source_id', 'canonical_work_id', 'title', 'authors_or_organization', 'venue_or_source', 'publication_date', 'url_or_doi', 'version', 'accessed_at', 'inspected_scope', 'read_status', 'relevant_claim', 'evidence_note', 'limitations', 'reviewer', 'reused_from'}
        for i, source in enumerate(evidence_records):
            path = f'evidence[{i}]'
            if not isinstance(source, dict):
                errors.append(f'{path} must be an object'); continue
            errors.extend(f'missing {path}.{key}' for key in sorted(required_source - source.keys()))
            sid, work = source.get('source_id'), source.get('canonical_work_id')
            if not numbered_id(sid, 'S'):
                errors.append(f'{path}.source_id must be S followed by at least 3 digits and a positive number')
            elif sid in source_ids:
                errors.append(f'duplicate source_id {sid}')
            else:
                source_ids.add(sid)
            if not nonempty(work):
                errors.append(f'{path}.canonical_work_id must be nonempty')
            elif work in works:
                errors.append(f'duplicate canonical_work_id {work}')
            else:
                works.add(work)
            if source.get('read_status') not in ('audited', 'full'):
                errors.append(f'{path}.read_status must be audited or full')
            full += source.get('read_status') == 'full'
            if not timestamp(source.get('accessed_at')):
                errors.append(f'{path}.accessed_at must be an ISO-8601 timestamp with timezone')
            prior = source.get('reused_from')
            if prior is not None and not nonempty(prior):
                errors.append(f'{path}.reused_from must be null or a nonempty string')
            inspected_now = source.get('inspected_in_run', prior is None)
            if type(inspected_now) is not bool:
                errors.append(f'{path}.inspected_in_run must be a boolean when present')
            reused += inspected_now is False
        for ref in sorted(set(citations) - source_ids):
            errors.append(f'unknown venue source_id {ref}')
        expected_counts = {'audited': len(evidence_records), 'fully_read': full,
                           'newly_inspected': len(evidence_records) - reused, 'reused': reused}
        for key, actual in counts.items():
            if actual != expected_counts[key]:
                errors.append(f'evidence_summary.{key} disagrees with ledger: expected {expected_counts[key]}')
    def forbidden(v):
        if isinstance(v, dict):
            return any(k == 'utility_score' or forbidden(x) for k, x in v.items())
        return isinstance(v, list) and any(forbidden(x) for x in v)
    if forbidden(r):
        errors.append('personal utility must not be scored')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--evidence', type=Path, help='JSONL ledger (default: evidence.jsonl beside RESULT)')
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.result.read_text(encoding='utf-8'))
        ledger_path = args.evidence if args.evidence is not None else args.result.parent / 'evidence.jsonl'
        records = None
        if args.evidence is not None or ledger_path.exists():
            records = []
            for number, line in enumerate(ledger_path.read_text(encoding='utf-8').splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError as exc:
                    raise ValueError(f'{ledger_path}:{number}: invalid JSON: {exc}') from exc
        issues = validate_report(report, evidence_records=records)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print('\n'.join(issues) if issues else 'OK: v2 structural and policy checks passed')
    return int(bool(issues))


if __name__ == '__main__':
    sys.exit(main())
