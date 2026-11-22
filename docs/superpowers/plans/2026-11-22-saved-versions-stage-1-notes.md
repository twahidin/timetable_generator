# Saved versions and Compare, stage 1: decisions made while building, and what was left

From the build ledger of `2026-11-22-saved-versions-stage-1.md` (design: `docs/superpowers/specs/2026-11-22-saved-versions-and-refit-design.md`). Built on branch saved-versions-1.

## Checked on the real files (counts and timings only)

The newest setup (the 20 November one) with the newest returned timetable that goes with it: 1,026 lessons (1,985 lesson rows), 32 classes, 111 teacher rows, 76 room rows, 10 days, 0 critical, 173 warnings. Everything ran through the app's own functions on a scratch data folder, which was deleted afterwards. Nothing was published, so the published-timetable comparison was not run on real files: two versions, and the draft against a saved version, were compared instead. `published_counts` with nothing published answered at once.

- Upload of the two files as a draft: 0.7 to 1.5 s.
- `versions.keep`: under 0.01 s; a second `keep` of the same draft (skipped by identity): under 0.01 s.
- One version folder: 883 KB.
- `draft.checked_in` of one folder: 0.3 to 0.9 s.
- `versions.listing` with 11 versions (10 saved by hand, 1 kept on upload): first call 3.9 s (every count worked out), cached 0.00 s, with `counts=False` 0.00 s. The route `GET /api/draft/versions` with the cache warm: 0.34 s.
- `versions.open_version`: 0.20 s. The draft was identical to the version opened (it had just been saved), so no "open" copy was kept and the count stayed at 11, as the keep rule says.
- `compare.diff`: version against version 0.84 s (9 lessons moved); draft against a hand-saved version 0.55 s (9 differences); draft against the upload-kind version 0.46 s (10 differences). The Excel file of a comparison: 0.67 s.

## Rulings made while building

- Listing counts are computed outside the lock and cached per setup version.
- `keep()` skips a draft whose identity matches any version.
- A version that cannot be read is never opened (the draft stays).
- A malformed version.json is skipped everywhere.
- `published_counts` degrades to an error figure instead of breaking the list, and caches by published stamp and setup version but never an error.
- A length change of a lesson at the same slot counts as a time difference.
- `replace` is accepted and ignored on uploads.
- `UnpublishedFixes` was removed.

## Checked in a browser

- Versions pop-out: Save, Open, Delete, Compare..., Esc, backdrop and Close, focus, phone width.
- Compare: the sources, Show, the marks, the Excel route, a bad id.
- An upload keeping a draft.

Not checked: the operating system's file picker and a real drag from the desktop; the Download buttons were not clicked because they save a file (their routes were checked); Delete's confirm dialog was stubbed; the empty school was not opened.

## Deferred small points

- A ".new" folder is left behind by a failed keep.
- A malformed version folder cannot be deleted through the app.
- Tests still send replace=1.
- Some colours are hard-coded in compare.html.
- The default-name test for Compare is weak.
- The same timetable is loaded up to three times per Compare request.
- The 409 no-setup path of the new routes is untested.
- Numeric fields are unescaped in the pop-out.
- `_involves` repeats `compare.week`'s rule.
- Keeping focus on macOS Safari and Firefox after a mouse click may use the name box.

## Held for stage 2 (re-fit)

- The `refit` kind is reserved. The re-fit's Apply calls `versions.keep("refit", by, name)` and writes a batch.
- Band changes go to "Needs you".
- Typed rules "allow and flag" (see the design).
