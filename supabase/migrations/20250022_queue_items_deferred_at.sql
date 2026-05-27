-- Phase 10-rev Step 2g — queue_items.deferred_at column.
--
-- When the user taps "not ready yet — come back later" on a problem before
-- starting it, the queue item transitions to state='deferred' (added to the
-- check constraint in 20250018) and deferred_at is set to now(). Step 3's
-- /check-deferred uses this timestamp to decide when to re-queue.
--
-- updated_at already exists but gets overwritten on every state change, so
-- it isn't a reliable "when was this deferred" signal. deferred_at is the
-- authoritative timestamp for the curator.

alter table public.queue_items
  add column deferred_at timestamptz;
