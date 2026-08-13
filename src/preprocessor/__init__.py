"""Evaluation-side preprocessor. PARKED - design agreed, implementation deferred.

Agreed boundary:
  belongs to the evaluation framework, not the system under test
  versioned under evaluation_version, never model_version
  ANNOTATES ONLY. It must never repair.

Because it will not exist in production, any repair it made would be a gap
between what was scored and what would reach a clinician. Permitted: native
format -> conformant schema, whitespace/encoding normalisation, hash
recomputation, emitting findings. Forbidden: extracting omitted claims, adding
or correcting citations, rewriting claim text, inferring an absent abstention
reason.

Open question, unresolved: whether to normalise citation ID case
("DOC_C001A" -> "doc_c001a"). Normalising rescues a citation that would
otherwise score as a gate-firing fabricated citation; not normalising blocks
release on a possibly cosmetic defect. If normalised, the counterfactual must be
reported.

Covered by 3.14.5: preprocessor instability invalidates the release decision.
"""
