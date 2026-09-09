# Rollback.md — Undo Procedures

## Prerequisite

Git in use from commit #1. **Status as of 2026-09-04: local and GitHub
confirmed in sync at commit `78eb529`** — independently verified via
fresh clone, not assumed. This is a known-good fallback point.

## Small Edit / Larger Change / Committed Change

Unchanged from prior version — `git restore`, `git stash`, `git revert`.
See prior regeneration for full detail; procedures haven't changed.

## Dependency Change

- **Frontend:** `package-lock.json` is tracked and was updated/committed
  this cycle. `npm ci` restores exact versions.
- **Backend:** Still no lockfile for Python deps; `scikit-learn` is now
  in `requirements.txt`. Still unpinned versions — DECISION REQUIRED if
  this becomes a problem.

## Emergency Recovery

```bash
git clone https://github.com/swwwayam/daisy.git daisy-recovery
```

Known-good fallback point as of this update: commit `78eb529`.

**Lesson from this cycle, reinforcing the earlier one (see prior Rollback.md
version):** the discipline of handing off real files immediately and
committing promptly was followed successfully throughout Model Selection,
Model Training, the frontend work, and the fallback fix — no repeat of
the earlier full-rebuild incident. This is now a proven pattern, not just
a stated intention.

## Secrets

Unchanged — `backend/.env` not tracked, not backed up by any rollback
procedure here.
