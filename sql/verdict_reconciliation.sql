-- Reconciliation report: the end-to-end account of the campaign, in the
-- API's own vocabulary (verdict x origin). Three views of the same state:
-- the funnel, the distinct-number campaign state, and the qualification of
-- each of the 10 000 referential rows. Structural motives are detailed
-- separately in motive_distribution.sql.
-- Run:
--   docker exec meridian_tva_db psql -U meridian -d tva -f - < sql/verdict_reconciliation.sql

-- 1. Funnel: referential rows -> VIES candidates -> distinct numbers (D2).
SELECT
    count(*)                                         AS rows_total,
    count(*) FILTER (WHERE NOT structural_candidate) AS structural_rejects,
    count(*) FILTER (WHERE structural_candidate)     AS vies_candidates,
    count(DISTINCT vat_number)                       AS distinct_numbers
FROM referential_rows;

-- 2. Campaign state over distinct numbers (NULL = never checked).
SELECT
    coalesce(vies_status, 'never_checked') AS vies_status,
    count(*)                               AS numbers
FROM vat_numbers
GROUP BY vies_status
ORDER BY numbers DESC;

-- 3. Row-level qualification: the verdict the API serves for each row.
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
