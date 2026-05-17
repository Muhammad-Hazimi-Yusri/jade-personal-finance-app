-- Migration 011: Re-categorise existing transfers
--
-- Previously the dashboard treated every negative-amount transaction as an
-- expense, inflating spending KPIs ~10× because pot transfers, Flex
-- repayments, and investment-provider payments were all counted. From this
-- migration onward `app/services/csv_parser.py` auto-categorises these on
-- import; this migration applies the same rules retroactively.
--
-- All three UPDATEs are conservative:
--   - Skip rows where the user has explicitly set custom_category.
--   - Skip rows already in the target category (no-op).
-- Safe to re-run via /api/transactions/recategorize-transfers.

UPDATE transactions
SET category = 'savings', updated_at = datetime('now')
WHERE type = 'Pot transfer'
  AND custom_category IS NULL
  AND category != 'savings';

UPDATE transactions
SET category = 'transfers', updated_at = datetime('now')
WHERE type = 'Flex' AND amount < 0
  AND custom_category IS NULL
  AND category != 'transfers';

UPDATE transactions
SET category = 'savings', updated_at = datetime('now')
WHERE type IN ('Faster payment', 'Bacs (Direct Credit)')
  AND custom_category IS NULL
  AND category NOT IN ('savings', 'transfers')
  AND (
    lower(name) LIKE '%moneybox%'
    OR lower(name) LIKE '%trading 212%'
    OR lower(name) LIKE '%seccl%'
  );
