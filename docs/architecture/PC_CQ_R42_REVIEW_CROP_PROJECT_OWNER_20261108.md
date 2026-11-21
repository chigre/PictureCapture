# PC-CQ R4.2 — cross-project crop callback ownership (2026-11-08)

## Failure-first evidence

Test-only `20da571882ec0efdb50a41907300d859e3352dc8`, `tests/test_r42_review_crop_project_owner_20261108.py`. [CI RED #42436390625](https://github.com/chigre/PictureCapture/actions/runs/42436390625): all six OS/Python matrix jobs failed on intended stale-success assertion; Ubuntu 3.13 1 failed, 5772 passed, 3 skipped. Same-project positive control passed.

## Minimal source correction

`ecdfe051aa6cb665bef993e8c5cfd921d450361b` changes only `src/picture_capture/ui/review_workspace_workflow.py`: `_request_render_rows().done` rejects results when `self.parent.project is not project`, matching existing failure-callback ownership protection. Existing page, entry, text, settings, zoom and viewport checks remain in force. No persistence or source-pixel coordinates changed.

## Exact source HEAD evidence

- [CI #42441136416](https://github.com/chigre/PictureCapture/actions/runs/42441136416): Windows/macOS/Ubuntu × Python 3.10/3.13 **6/6 SUCCESS**, Risk tier and Risk-tier CI gate **SUCCESS**.
- [OCR #42441136121](https://github.com/chigre/PictureCapture/actions/runs/42441136121): Windows/macOS/Ubuntu **3/3 SUCCESS**.
- [CodeQL #42441134024](https://github.com/chigre/PictureCapture/actions/runs/42441134024): Python and Actions **2/2 SUCCESS**; exact commit check-runs independently show both Analyze jobs SUCCESS.
- Documentation architecture check **SKIPPED, not PASS**.

These are synthetic E2 checks, not real-user acceptance. No claim of actual corrupted files, atomic cross-file writes, rollback or performance improvement. This audit/checkpoint commit must be validated on its own exact HEAD. Manual Windows E3, #483 W1–W11, #503 Undo/Redo, real dictionary scans and PDIC/PPP/SECTION/Profile/OCR save-reopen, R6 real labels and R8 scans remain NOT PERFORMED/DEFERRED.
