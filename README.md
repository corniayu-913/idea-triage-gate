# Idea Editor / Idea Triage Gate v2

A portable agent prompt pack for opening research topics: **academic potential out of 10, venue positioning, and GO/NO-GO against your criteria**. An unbuilt system, unwritten proof, or unrun experiment is normal at this stage, not a reason to reject an idea. Personal utility remains your decision.

## Use

Read [the entry guide](prompts/00-start.md), or give an agent this repository and ask:

> Use $idea-triage-gate on this idea: [idea]. My minimum academic score is 7/10. Preferred venues: [venues]. Confirm your interpretation before searching. I will decide personal utility.

Mandatory venue conditions must be explicit; preferences are nonbinding. Without a threshold or other binding condition, the agent completes scoring and venue suggestions and leaves the gate pending. Scores do not map mechanically to CCF categories or individual venues.

For Codex skill installation, clone this repository into your own skill directory as `idea-triage-gate`. This repository does not install itself or start a hosted agent.

## Prompt files

- [Lead editor](prompts/01-editor.md): intake, confirmation, orchestration, synthesis.
- [Novelty reviewer](prompts/02-novelty-reviewer.md): closest work and contribution delta.
- [Problem reviewer](prompts/03-problem-reviewer.md): problem evidence and significance, no utility score.
- [Scoring and venues](prompts/04-scoring-and-venues.md): 1–10 rubric and policy-relative gate.
- [Files and state](prompts/05-files-and-state.md): private idea directories, immutable runs, source ledger, structured result.
- [Report template](prompts/06-report-template.md): consistent assessment output.
- [Parallel reading](prompts/07-parallel-reading.md): shared queue, per-paper prompt, up to 10 simultaneous reads subject to host capacity.

A/B are analytical responsibilities, not a two-worker limit. Concurrent reads and total reading budgets are distinct. The default total ceilings remain 100 audited works and 15 full reads; they are ceilings, not quotas. A prompt cannot supply unavailable tools or worker capacity.

## Validation

```bash
python tests/run_skill_validation.py
python scripts/validate_assessment.py examples/assessment-v2.json
python -m unittest discover -s tests -p 'test_*.py'
```

These checks validate structure and policy consistency, not scientific truth or actual tool execution. The example is synthetic, not a real assessed idea or literature search.

For real assessments, the CLI automatically reads `evidence.jsonl` beside the
result. A ledger is required when a venue cites a source or evidence counts are
nonzero. To use a different ledger location:

```bash
python scripts/validate_assessment.py path/to/result.json --evidence path/to/evidence.jsonl
```

Python callers pass the parsed JSONL records as
`validate_report(report, evidence_records=records)`. The existing one-argument
call still supports zero-source records such as the shipped synthetic example;
it reports a missing-ledger error when cross-file validation is necessary.
The validator now checks confirmation provenance, required academic explanations,
identifiers and timestamps, preference types, venue source references, and ledger
counts. See the [validation contract](prompts/05-files-and-state.md#validator-contract)
for count semantics and unknown values. No network requests are made.

## Migration from v1

The former resource-aware BUILD/TEST/PARK/KILL workflow and its 0–4 ratings are archived under [legacy/v1](legacy/v1). They are no longer the default. Old reports remain readable with `python legacy/v1/scripts/validate_idea_gate.py legacy/v1/examples/idea-gate.json`. No automatic conversion of scores or verdicts is valid.

Keep private idea inputs and reports outside this public repository. v2 defines an agent workflow; it does not include a scheduler or deployed runtime.

Maintained by Hanyue Shen, Founder at YH Intelligence Technology, Co., Ltd. Contact: hanyueshen@yh-intel.com.

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
