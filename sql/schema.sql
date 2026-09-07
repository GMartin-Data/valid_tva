-- Schema for the VAT referential. Single source of truth for the data model;
-- design rationale in docs/architecture.md (decisions D1-D4).
-- Idempotent: safe to re-apply at every load.

-- Distinct canonical numbers (dedup key D2: country || national).
-- Carries the OBSERVED, perishable data: the VIES verdict and its date.
-- vies_status semantics: NULL = never checked; 'unknown' = checked but the
-- service could not answer (never conflated with 'invalid' - brief criterion).
CREATE TABLE IF NOT EXISTS vat_numbers (
    vat_number      text PRIMARY KEY,
    country         text NOT NULL,
    national        text NOT NULL,
    vies_status     text CHECK (vies_status IN ('valid', 'invalid', 'unknown')),
    vies_checked_at timestamptz,
    vies_name       text,
    vies_address    text
);

-- The 10 000 referential rows, exactly one per CSV line.
-- RECEIVED columns are stored untouched; DEDUCED columns are recomputed at
-- every load (deterministic module). A rejected row never reaches the VIES
-- stage, hence its vat_number stays NULL.
CREATE TABLE IF NOT EXISTS referential_rows (
    id                   integer PRIMARY KEY,
    raison_sociale       text NOT NULL,
    pays_declare         text NOT NULL,
    numero_tva_raw       text NOT NULL,
    date_saisie          date NOT NULL,
    source_saisie        text NOT NULL,
    normalized           text,
    country              text,
    prefix_added         boolean NOT NULL DEFAULT false,
    structural_candidate boolean NOT NULL,
    structural_motive    text,
    vat_number           text REFERENCES vat_numbers (vat_number),
    CHECK (structural_candidate = (structural_motive IS NULL)),
    CHECK (vat_number IS NULL OR structural_candidate)
);

CREATE INDEX IF NOT EXISTS idx_rows_motive ON referential_rows (structural_motive);
CREATE INDEX IF NOT EXISTS idx_rows_vat_number ON referential_rows (vat_number);
