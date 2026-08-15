# How to Run the BARN-AIS-EVAL-001 Harness — Step by Step

## Prerequisites

```bash
cd /path/to/javad-hezareh-barnabus-assignment
```

### 1. Create the venv and install dependencies

```bash
make install
```
This creates `.venv/`, installs pinned deps, and installs `barn_eval` as an editable package.

### 2. Set the OpenRouter API key (required for the LLM judge)

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```
The key is read from the environment only (see `src/barn_eval/judge/client.py`) — it must never go in configs.

---

## The Pipeline (what `make eval` does)

`make eval` runs `.venv/bin/python -m barn_eval.cli run --config configs/run.default.yaml`. Internally, `runner.py` executes 7 steps:

| Step | What happens | Key source |
|---|---|---|
| **1. Load + Preconditions** | Reads all case JSONL files + patient JSON. Validates against `evaluation_case.schema.json`. Runs registry checks (patient IDs match, document hashes valid, etc.) | `loaders.py`, `registry_checks.py` |
| **2. Load responses** | Reads the JSONL response file (path from config `data.responses`). Validates against `model_response.schema.json`. Also loads confirmations. | `loaders.py` |
| **3. Join** | Matches responses to cases by `case_id`. Cases with no response get `status=missing_response` but stay in every denominator (never silently dropped). | `join.py` |
| **4. Score** | Runs **8 deterministic scorers** (always) + **8 judge scorers** (if judge enabled) against each joined record. | `scorers/` |
| **5. Aggregate** | Maps findings → severity levels via `configs/severity_map.yaml`, computes rates, evaluates 5 release gates against `configs/thresholds.yaml`. | `aggregation/` |
| **6. Write outputs** | `result.json`, `findings.jsonl`, `run_metadata.json`, summary + evaluation card → `results/runs/<run_id>/` | `reporting/` |
| **7. Exit code** | `0` = completed (BLOCK/PASS is the payload, not error), `1` = missing responses, `2` = registry/schema broken | `runner.py` |

### Deterministic Scorers (no LLM, always run)

| Scorer | What it checks |
|---|---|
| `CitationScorer` | Fabricated citations (source_id not in retrieved docs) |
| `ContaminationScorer` | Gold leakage / answer-key contamination |
| `AuthorityScorer` | Evidence authority tier violations (E0–E5) |
| `AbstentionScorer` | Appropriate abstention behaviour |
| `PatientContextScorer` | Patient context usage |
| `RetrievalScorer` | Recall@K metrics |
| `IntegrityScorer` | Content hash verification, provenance chain |
| `CostScorer` | Cost tracking |

### Judge Scorers (require OpenRouter API key + live model)

| Scorer | What it checks |
|---|---|
| `GroundednessScorer` | Are claims supported by retrieved docs? |
| `CorrectnessScorer` | Does answer match expected conclusion? |
| `DecisionRelevanceScorer` | Are claims clinically decision-relevant? |
| `ProhibitedClaimScorer` | Does response make any prohibited claims? |
| `GapSpecificityScorer` | Quality of abstention gap descriptions |
| `ConflictHandlingScorer` | How evidence conflicts are handled |
| `StalenessHandlingScorer` | How stale evidence is handled |
| `InjectionResistanceScorer` | Resistance to prompt injection in docs |

### 5 Release Gates

| Gate | Condition | Status if not evaluable |
|---|---|---|
| **Gate 1** | Zero critical safety failures | — |
| **Gate 2** | Zero fabricated citations on decision-relevant claims | — |
| **Gate 3** | Zero evidence authority violations | — |
| **Gate 4** | Clean→adversarial degradation within thresholds | `NOT_EVALUABLE` (no adversarial cases) |
| **Gate 5** | Evaluator instability (Phase 6 reliability) | `NOT_EVALUATED` (Phase 6 not implemented) |

Final recommendation: **BLOCK** (any gate fails), **PROVISIONAL_PASS** (gates pass but some not evaluated), or **PASS** (all clear).

---

## Running the Commands

### Step 3: Validate (schema + registry only, no scoring)

```bash
make validate
# or with a custom config:
make validate CONFIG=configs/run.generated_clean.yaml
```

### Step 4: Full evaluation run

```bash
make eval
# or with a custom config:
make eval CONFIG=configs/run.generated_clean.yaml
```

### Step 5: View report from a previous run

```bash
make report                              # latest run
make report CONFIG=configs/run.default.yaml  # specific config
```

### Step 6: Run tests (offline, no API key needed)

```bash
make test
```

---

## Config File Anatomy (`run.default.yaml`)

| Section | Key fields |
|---|---|
| `run` | `seed`, `evaluation_version`, `experiment_id`, `output_dir` |
| `data` | `patients` (JSON), `cases` (list of JSONL globs), `responses` (JSONL), `confirmations` (dir) |
| `response_source` | `simulated_fixture` or `rag_prototype` (Gate 2: never report a fixture as a system result) |
| `retrieval` | `k`, `ordering_policy` |
| `judge` | `enabled`, `model`, `api_key_env`, `temperature`, `timeout`, `max_retries`, `request_interval` |
| `failure_handling` | `on_missing_response: record`, `exit_nonzero_on_missing: true` |
| `paths` | `severity_map`, `thresholds` — the two files that control scoring arithmetic |

## Outputs (what a run leaves behind)

```text
results/runs/<run_id>/
  result.json           # full aggregate: gates, rates, per-case failures, integrity
  findings.jsonl        # every individual scorer finding
  run_metadata.json     # model, seed, versions, timestamp, git SHA
  summary.txt           # human-readable summary
  evaluation_card.md    # formatted evaluation card
```
