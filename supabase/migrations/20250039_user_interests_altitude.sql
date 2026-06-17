-- Phase 13 Step 3: per-interest altitude signal.
-- Values: 'new' | 'coming_back' | 'go_deep'.
-- Orthogonal to path_json — you can be 'new' or 'go_deep' on the same path.
-- Drives intent (teach/refresh/consolidate) and entry-lane (§3.4) at generation
-- time. Null means no signal collected yet; generation falls back to
-- intent_context prose matching (existing behaviour preserved for old rows).
ALTER TABLE user_interests
  ADD COLUMN IF NOT EXISTS altitude TEXT
    CHECK (altitude IN ('new', 'coming_back', 'go_deep'));
