-- Phase 13 Step 2: add path_json to user_interests.
-- Stores the structured path facts (mode_lean, leans_on, endpoint, etc.)
-- chosen when the user picks a path for an ambiguous interest.
-- Null = no path chosen (specific interest, or user skipped).
-- The curator reads mode_lean and leans_on as field reads from this column;
-- intent_context remains the prose narrative and is not duplicated here.
ALTER TABLE user_interests ADD COLUMN IF NOT EXISTS path_json JSONB;
