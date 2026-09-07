-- Structural verdict distribution by motive (end-of-J1 testable result).
-- Candidates appear under the CANDIDATE label.
SELECT
    coalesce(structural_motive, 'CANDIDATE') AS motive,
    count(*)                                 AS rows
FROM referential_rows
GROUP BY structural_motive
ORDER BY rows DESC;
