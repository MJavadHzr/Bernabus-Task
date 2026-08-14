"""Exact checks. Exempt from the 5 reliability burden by construction.

The directory listing IS the §5 exemption list: everything here is deterministic
and does not go through the LLM judge. `DETERMINISTIC_SCORERS` is the ordered set
the runner instantiates.
"""

from .abstention import AbstentionScorer
from .authority import AuthorityScorer
from .citations import CitationScorer
from .contamination import ContaminationScorer
from .cost import CostScorer
from .integrity import IntegrityScorer
from .patient_context import PatientContextScorer
from .retrieval import RetrievalScorer

DETERMINISTIC_SCORERS = [
    CitationScorer,
    ContaminationScorer,
    AuthorityScorer,
    AbstentionScorer,
    PatientContextScorer,
    RetrievalScorer,
    IntegrityScorer,
    CostScorer,
]

__all__ = [
    "AbstentionScorer",
    "AuthorityScorer",
    "CitationScorer",
    "ContaminationScorer",
    "CostScorer",
    "IntegrityScorer",
    "PatientContextScorer",
    "RetrievalScorer",
    "DETERMINISTIC_SCORERS",
]
