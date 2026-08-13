"""Evidence integrity and provenance completeness (Part Four requirement 5).

  content_hash equals sha256(content) for every cited document
  every citation resolves to a document in the case
  source_version, source_date and source_authority are non-null where cited

Also emits the per-response provenance record Part Four requires: source ID,
version, date, authority, content hash, retrieval score, evidence authority
level, supporting text span, model version, prompt version, evaluation version.
"""
