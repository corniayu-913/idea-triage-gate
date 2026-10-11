# File Management and State Contract

Keep prompt definitions separate from private assessment data. Never place private idea records into a public prompt repository by default. Use the user's designated persistent workspace; if absent, use the host's authorized persistent artifact location. If persistence is unavailable, return the files and disclose that limitation. Never claim these instructions implement a database or runtime.

## Naming

- Prompt package: `idea-editor-agent/`, version 2.0.
- Assessment root: `idea-assessments/`.
- Idea directory: `YYYY-MM-DD--short-kebab-slug--xxxxxxxx/`, where the date uses the user's timezone and the suffix is 8 random hexadecimal characters. Check collision and regenerate if needed.
- Stable idea ID: the directory name, unchanged if the title changes.
- Runs: `runs/r001/`, `runs/r002/`, etc.; allocate sequentially without overwriting an existing run.
- Idea revision: `i001`, `i002`, etc.; increment only when the problem, method, scope, or contribution materially changes. A new evidence search can create a new run for the same idea revision.
- Use lowercase ASCII kebab-case filenames, relative paths inside manifests, UTF-8 text, and ISO-8601 timestamps with timezone offsets. Do not use “final-final” or overwrite historical reports.

## Per-idea files

| Path | Content and owner |
|---|---|
| `source.md` | Original user input, preserved verbatim; lead creates once |
| `state.json` | Current idea revision, active/latest complete run, phase, prompt version; lead only |
| `runs/rNNN/intake.md` | Confirmed representation, user corrections, assumptions, confirmation/waiver evidence |
| `runs/rNNN/policy.json` | Exact user policy and normalized binding criteria |
| `runs/rNNN/novelty.md` | Novelty reviewer memo |
| `runs/rNNN/novelty-sources.jsonl` | Novelty reviewer's candidate source records |
| `runs/rNNN/problem.md` | Problem reviewer memo |
| `runs/rNNN/problem-sources.jsonl` | Problem reviewer's candidate source records |
| `runs/rNNN/evidence.jsonl` | Lead-merged, deduplicated source register |
| `runs/rNNN/reading-queue.json` | Lead-owned work states, reservations, concurrency and budget counters |
| `runs/rNNN/readings/SNNN.md` | One assigned reader's source-level evidence note; finalized by the lead |
| `runs/rNNN/report.md` | Human-readable report |
| `runs/rNNN/result.json` | Structured result, lead only |

Do not create fake reviewer outputs for unexecuted work. Record fallback passes honestly. Do not bulk-download papers unless necessary and permitted. Store citations and inspected-scope notes instead.

## State and resuming

Phases: awaiting_confirmation, reviewing, synthesizing, awaiting_policy, complete, incomplete. Awaiting policy may have a complete academic report; it is only the gate that is pending.

On resume read this pack, `state.json`, and the active run's intake, policy, evidence, and latest result. Load other memos as needed. Do not rely on conversational memory for confirmation or prior scores. Missing records are missing, not permission to infer them. Explicit reset creates a fresh run and clears prior judgment as authority while preserving history. Reuse previous sources only after checking their relevance and currentness; distinguish reused records from newly inspected sources.

The lead allocates runs and is the only shared-state writer. Reviewers receive fixed output paths and never edit each other's files. Use a host-supported lock or single-writer serialization, and atomic temp-file replacement for mutable pointers where available. An interrupted run must not replace the latest complete pointer. Finalized run artifacts are immutable; corrections create a new run with a reference to the previous one.

Per-paper workers write distinct attempt files `readings/SNNN--attempt-NN.md`; the lead selects the successful note as `readings/SNNN.md`. Queue updates are serialized by the lead. A/B request sources through the lead and may both consume the same factual note without sharing their independent initial judgments. Reserve source IDs before dispatch; retain them during final merge and remap aliases rather than renumbering completed notes.

## Source record

One JSON object per line: source_id, canonical_work_id, title, authors_or_organization, venue_or_source, publication_date, url_or_doi, version, accessed_at, inspected_scope, read_status (audited or full), relevant_claim, evidence_note, limitations, reviewer, reused_from (null or prior run). Missing values are null, never invented. A full read also counts as audited. Lead assigns stable local IDs S001, S002, etc. and maps reviewer IDs before final citation. Reused uninspected records do not count as newly audited; report both totals separately.

## Structured result

`result.json` uses schema_version `2.0` with:

- idea_id, idea_revision, run_id, prompt_version, assessed_at;
- confirmation: status (confirmed / waived / awaiting), evidence_reference;
- academic: score (integer 1–10 or null), confidence (low / medium / high or null), rationale, novelty_delta, significance, contribution_depth;
- policy: minimum_score (integer 1–10 or null), mandatory_venue_criteria (array), preferred_venues (array), user_instruction_reference;
- gate: verdict (GO / NO-GO / null), status (decided / awaiting_policy / incomplete), criteria_checks (array of objects with criterion, status = met/not_met/unknown, reason; use criterion `minimum_score` for the score threshold and the exact mandatory criterion string for each venue condition), rationale;
- venues: array of name, track, fit, positioning, requirements, source_ids;
- value_evidence: optional descriptive observations, explicitly without utility scores;
- research_obligations, decisive_unknowns, evidence_summary, prior_run_reference.

Use null for genuinely unavailable values, never invented placeholder scores. Do not include a utility_score field.

## Validator contract

`python scripts/validate_assessment.py RESULT.json` loads the sibling
`evidence.jsonl` if present. `--evidence FILE.jsonl` overrides that location and
requires the named file to exist. The Python API is
`validate_report(report, evidence_records=None)`; pass a list of parsed records
when sources have been registered. Nonzero evidence counts or venue citations
without a ledger fail validation. An empty zero-source record does not require
a ledger; a malformed ledger is never silently ignored.

- All listed nested result fields are required. Confirmed or waived records need
  a nonempty `confirmation.evidence_reference`. Awaiting records may use null.
  This field may cite a message or a file in prose: validation establishes its
  presence, not actual user consent, file existence, or the truth of a waiver.
- A scored assessment needs nonempty rationale, novelty_delta, significance and
  contribution_depth. For unscored incomplete records, these fields may be null
  when unknown, but must remain present. Do not invent explanations to pass.
- `idea_revision` and `run_id` use i/r plus at least three digits with a positive
  number; sequences may exceed 999. Idea IDs follow the dated slug/hash naming
  rule and use a valid calendar date. The shipped `synthetic-example` ID remains
  allowed only when `evidence_summary.synthetic` is the Boolean true; other
  `synthetic-<slug>` fixtures follow the same explicit exception.
- `assessed_at` and source `accessed_at` use ISO-8601 date-times with seconds and
  a timezone offset or Z. `preferred_venues` is an array of nonempty strings.
  Venue records require name, track, fit, positioning, requirements and
  source_ids. Track may be null; requirements and source_ids are string arrays.
  Positioning is stretch / plausible target / more conservative target. Empty
  source_ids do not verify a venue claim; disclose unavailable scope evidence.
- Evidence records contain every field listed under Source record; unavailable
  metadata may be null. Stable source_id, canonical_work_id, read_status and
  accessed_at cannot be unknown. Duplicate source IDs or work families fail.
  Every venue source ID must resolve to this ledger.
- `evidence_summary.audited` and `fully_read` are required nonnegative integers
  (booleans do not count as integers). They are cumulative unique registered
  sources and the subset marked full, respectively, including reused sources.
  Both must match the ledger, and fully_read cannot exceed audited.
- Optional `newly_inspected` and `reused` are nonnegative counts that must match
  the ledger when present. By default a source with reused_from=null is newly
  inspected; a prior-run reference means reused without reinspection. A source
  may explicitly set the optional Boolean `inspected_in_run` to record whether
  it was actually inspected in this run, including reinspection of a prior
  source. Reused means not inspected in this run for these summary counters;
  both counters partition audited. Provenance stays in reused_from.

This validator checks recorded consistency, not whether a claimed reading took
place, whether a DOI resolves, or whether the research claims are true. Keep the
independent review and completion checks below.

## Completion checks

Check score range, IDs, confirmation or explicit waiver, source references, actual counts, and report/result agreement. Recompute gate from the recorded policy: all met gives GO, any not_met gives NO-GO, otherwise null; empty binding criteria gives awaiting_policy. Ensure missing implementation is not a failing criterion. Check that all reported agent runs actually occurred. Structural consistency does not certify scholarly truth.

For a policy-only change, create a new run referencing the prior academic assessment, preserve its score/date and sources, and recompute only the gate. Do not claim a new literature search or count reused sources as newly read.
