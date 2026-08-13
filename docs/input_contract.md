# Harness Input Contract — BARN-AIS-EVAL-001

This is the canonical input contract for the evaluation harness. It defines two file types plus the fields the harness computes itself at scoring time. Formal machine-checkable schemas: `evaluation_case.schema.json`, `model_response.schema.json`.

## 1. Two files, two authors

| File | Location | Authored by | Contains |
|---|---|---|---|
| Evaluation case | `evaluation_cases/*.jsonl` | Eval team (gold/expected) | Question, documents, patient context, expected outcome |
| Model response | `results/responses/*.jsonl` | RAG system, or a parser translating its raw output into this schema | Answer text, claims, citations, abstention |

Both are joined by `case_id` at scoring time into one canonical `EvaluationRecord`. Case files never depend on response content; response files never depend on gold labels — this lets responses be regenerated without touching test cases, and vice versa.

## 2. If the RAG system doesn't emit this schema natively

Insert a **translator/parser module** between the raw system output and the harness: raw text/JSON in → `model_response.schema.json`-conformant record out. The harness's scorers only ever see the conformant schema — they have no knowledge of the system's native output format. This isolates parsing brittleness to one module instead of spreading format-handling logic across every metric.

## 3. Harness-computed fields (never authored, added during scoring)

These do not appear in either input file — they're derived when the harness joins a case with its response:

- `supporting_text_span` (per claim × citation pair) — the specific passage within the cited document that backs the claim; enables overreach detection (§3.4) beyond simple citation-existence checking.
- `status: "ok" | "missing_response"` (per joined record) — every case_id gets a record even with no matching response; nothing is silently dropped from the aggregate denominator.
- Run-level metadata: `evaluation_version`, `run_id`, `seed`, `timestamp`.

## 4. Join semantics

- Join key: `case_id`, exact match.
- A case with no matching response is **not** a crash — it's recorded as `status: "missing_response"` and included in the run summary's loud, non-zero-exit-code count. Evaluation continues for all other cases.
- A response with no matching case is a data-integrity error and should be logged and excluded (it can't be scored against gold that doesn't exist).

## 5. Design notes / rationale (for reviewers)

- `decision_relevant_criteria` (gold) is expressed as content/topic-match rules, not `claim_id` references — claim IDs don't exist until the system responds, so gold can't reference them at authoring time.
- `prohibited_claims` carries per-claim `severity` (not a flat list) because a critical-severity match (e.g. self-harm-adjacent claims) must gate the release decision (§3.15 → §3.12), while a moderate-severity match should only feed harm-weighting, not block release.
- `is_distractor` is explicit on documents rather than inferred from "retrieved but not required," so distractor-resistance test intent (Part Three, category 10) is self-documenting and doesn't depend on reverse-engineering absence.
- `injected_instructions` is a list (not a single flag) because prompt-injection resistance (§4.4) is scored per instruction, not per case — a single case may embed multiple directives with partial compliance.
- `content_hash` on retrieved documents supports evidence-integrity checking — proof a cited document wasn't altered between case authoring and evaluation run.
