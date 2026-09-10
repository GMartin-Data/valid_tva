-- Reconciliation report (brief deliverable): valid / invalid / unknown,
-- rejection motives and duplicates, in the API's own vocabulary
-- (verdict x origin). Four views of the same state: the funnel, the
-- rejection motives, the distinct-number campaign state, and the
-- qualification of each of the 10 000 referential rows.
-- Run:
--   docker exec -i meridian_tva_db psql -U meridian -d tva -f - < sql/verdict_reconciliation.sql

-- 1. Funnel: referential rows -> VIES candidates -> distinct numbers,
--    duplicates made explicit (D2: same country + normalized number).
SELECT
    count(*)                                         AS rows_total,
    count(*) FILTER (WHERE NOT structural_candidate) AS structural_rejects,
    count(*) FILTER (WHERE structural_candidate)     AS vies_candidates,
    count(DISTINCT vat_number)                       AS distinct_numbers,
    count(*) FILTER (WHERE structural_candidate)
        - count(DISTINCT vat_number)                 AS duplicate_rows
FROM referential_rows;

-- 2. Rejection motives (structural sieve: first sieve that stops, D4).
SELECT
    structural_motive AS motive,
    count(*)          AS rows
FROM referential_rows
WHERE structural_motive IS NOT NULL
GROUP BY structural_motive
ORDER BY rows DESC;

-- 3. Campaign state over distinct numbers (NULL = never checked).
SELECT
    coalesce(vies_status, 'never_checked') AS vies_status,
    count(*)                               AS numbers
FROM vat_numbers
GROUP BY vies_status
ORDER BY numbers DESC;

-- 4. Row-level qualification: the verdict the API serves for each row.
SELECT
    CASE
        WHEN r.structural_motive IS NOT NULL THEN 'invalid'
        WHEN v.vies_status IS NULL           THEN 'unknown'
        ELSE v.vies_status
    END      AS verdict,
    CASE
        WHEN r.structural_motive IS NOT NULL THEN 'structural'
        WHEN v.vies_status IS NULL           THEN 'never_checked'
        ELSE 'vies'
    END      AS origin,
    count(*) AS rows
FROM referential_rows r
LEFT JOIN vat_numbers v USING (vat_number)
GROUP BY 1, 2
ORDER BY rows DESC;
