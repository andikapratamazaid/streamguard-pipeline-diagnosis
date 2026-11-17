# Runbook RB-05: Configuration Error

**Category:** Configuration Error
**Typical symptoms:** recent configuration change, authentication failure spike, schema mismatch errors (often appearing right after a deployment)
**First response target:** 10 minutes from alert

## 1. Confirm the problem

1. Establish the timeline first: when did symptoms start, and what changed in the hour before? Configuration errors almost always have a change within the blast window.
2. Pull the change log for the affected component and list every change, including the ones marked trivial.

## 2. Diagnose

1. Diff the current configuration against the last known good version. Read the diff line by line; the offending line is usually a unit, a limit, or a permission.
2. Known repeat offenders in this category:
   - Retention values entered in the wrong unit (hours instead of days), which then shows up as disk pressure.
   - ACL changes that revoke the connector service account, which then shows up as authentication failures.
   - Schema registry compatibility raised without a migration, which then shows up as schema mismatch errors on producers.
   - Resource limit typos, for example a thread pool set to 1 instead of 16, which then shows up as indexing latency.
3. Confirm the blast radius: which components read the changed setting, and are all symptoms explained by it?

## 3. Fix

1. Roll back the single offending setting, not the whole change set. Whole-set rollbacks reintroduce the changes that were actually wanted.
2. Restore altered permissions or compatibility levels using the principle of least privilege; do not fix an ACL problem by granting broad access.
3. Restart only the component that reads the setting, so the corrected value takes effect with minimal blast radius.
4. Record the rollback in the incident record and in the change log, linked to the original change.

## 4. Verify

1. Run the smoke test: produce, consume, and index one synthetic record end to end.
2. Watch the symptom metrics for 30 minutes; configuration fixes take effect fast, so a slow recovery means the diagnosis was wrong.
3. Confirm no second component is still running with the bad value (rolling deployments can leave mixed versions).

## 5. Escalate when

- No change in the log explains the symptoms (treat as a different category and re-diagnose).
- The bad configuration has caused data loss, for example retention shortened long enough to delete data. Escalate to the incident commander immediately.

## 6. Prevention

- Two-person review for the configuration classes named in this runbook.
- Automated configuration diff alerts on production changes, posted to the on-call channel.
- Unit-explicit setting names (for example retention_hours, never a bare retention value).
