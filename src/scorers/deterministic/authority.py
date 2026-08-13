"""3.17 evidence authority violation. Three types, all deterministic.

  promotion by assertion     asserted_authority in E0-E3 on a generated claim
  unauthorised E4 -> E5      E5 with no confirmation, or an unauthorised actor
  broken provenance          confirmed_text_hash no longer matches the claim text

asserted_authority null is interpreted as E4 (an AI-generated draft is never
primary evidence) and cannot violate type 1.

Scope limit: this detects violations PRESENT IN THE RESPONSE RECORD. It does not
verify the pipeline's promotion logic, which is not observable from a response -
that is src/authority/, demonstrated by construction.
"""
