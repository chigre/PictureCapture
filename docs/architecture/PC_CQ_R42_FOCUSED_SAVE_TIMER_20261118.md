# R4.2 focused review save timers

## Save completion

The focused review `StringVar` trace mirrors each edit into the pending queue keyed by page and source XY. While a save is running, a subsequent edit can schedule a 160 ms debounce. A successful callback rebased the pending edit on the verified PDIC word and armed a 1 ms follow-up, but left the former debounce active. On a PDIC conflict, that debounce could dispatch another save attempt even though the completion path withheld a follow-up.

`focused_filter_workflow.py` now cancels the tracked debounce when the current, acknowledged dispatch accepts its first terminal callback. This happens before reconciliation or any conflict dialog. Successful completion can arm one follow-up for the latest text. Conflict and failure callbacks retain pending edits. A stale or duplicate worker callback still cannot cancel work belonging to a later dispatch.

## Shared periodic autosave

The main-window autosave timer called the focused review's immediate flush with explicit-retry permission even when the previous launch or PDIC outcome required inspection. `review_page_lifecycle.py` checks both existing uncertainty flags before taking that path. An unresolved focused save still consumes the tick for PDIC, so the main window cannot fall back to its own writer. Independent PPP saving and timer re-arming still run. The explicit ReviewWindow Save action can retry through the guarded writer.

## Main-window page navigation

The main page-selection coordinator also called focused `save()` through its explicit-retry path. A normal page change after a refused launch dispatched a new writer while ultimately refusing the navigation. The coordinator now refuses navigation before calling `save()` if the focused launch or disk outcome is unresolved. A normal pending edit still enters the guarded save before navigation. The separate explicit Save action still handles retry.

## Regression evidence

- Debounce [test-only commit](https://github.com/chigre/PictureCapture/commit/e8ae9b01a8a27b4ed67597afb3e595095eb5dfe5) locally reproduced 2 failures. The already-expired debounce and in-flight reversion controls passed. A real Tcl `StringVar` drove successive edits and the existing atomic writer published and read back synthetic PDIC. The test controlled timer and worker delivery without time-based sleeps.
- Periodic retry [test-only commit](https://github.com/chigre/PictureCapture/commit/d0115349611b32e8bf6a005622553fb833b56b8f) locally reproduced 2 additional failures with 5 passing controls. It exercised the shared main autosave entry point after a refused launch and after synthetic PDIC publication followed by an error. A healthy pending edit and a deliberate retry after inspecting the refused launch are covered.
- The combined source [commit](https://github.com/chigre/PictureCapture/commit/6429f897648e0399cf4409c457972cb47d496e40) passed 7 new cases, 240 related tests and the full local Python 3.12 suite (5798 passed, 3 skipped, 2 Pillow deprecation warnings). Architecture guard, change guard, F821 and diff checks passed. Diff classification and remote Windows/macOS/Ubuntu, OCR and CodeQL results must be read for the live checkpoint HEAD. The execution host did not provide a usable X display for local native GUI smoke.
- The first checkpoint's Windows Python 3.13 [job](https://github.com/chigre/PictureCapture/actions/runs/44248415909/job/134612973714) reported 6 failures, all from LF-only fixture expectations compared with PDIC's native CRLF output. The follow-up makes both synthetic input and expected output use native line endings and retains exact byte assertions for the whole row. Production code is identical to the first checkpoint. Verify all gates on the live follow-up HEAD.

- The page-navigation [test-only commit](https://github.com/chigre/PictureCapture/commit/5f22ddf941900417c5cdfbea0cf4eb3f2c8cfee2) locally yielded 1 expected failure and 8 passing cases. The [repair](https://github.com/chigre/PictureCapture/commit/04fa0f21254eb5376fa1ab84ee06f6ab49fe8581) passed all 9 new cases, 249 related tests and 5800 full local tests (3 skipped, 2 existing deprecation warnings). All 9 focused cases also passed with simulated native CRLF output. Architecture and F821 checks passed. The navigation fix retains the existing staged edits and blocks a retry before writer dispatch.

The changes are confined to focused save scheduling and the shared periodic and page-navigation entry points. The guarded writer, image/SECTION attestation, coordinates and persisted formats were retained. Windows E3, #483 W1–W11, #503 Undo/Redo, real scanning and real project save/reopen, R6 real-label learning and R8 real scanning remain deferred.
