# PC-CQ R4.2: same-stem different-path ReviewWindow crop callback owner (2026-11-08)

## Source-grounded defect and scope

In `src/picture_capture/ui/review_workspace_workflow.py::_request_render_rows()`, an asynchronous crop request can outlive a navigation to a different page within the same project. Different page paths can share a filename stem, so a `stem`-only comparison did not establish page ownership. Existing project, geometry, Entry and live-text checks were insufficient for this specific case when those witnesses coincided. This audit does not claim a broader atomic persistence or OS-level guarantee.

## RED-first witness and minimum correction

Test-only `0c696a944d634d063daeb0a0fc60ea381dd94d39` added `tests/test_r42_review_crop_page_path_owner_20261108.py` with a negative same-stem/different-path case and a positive unchanged-page case. [CI #42457329596](https://github.com/chigre/PictureCapture/actions/runs/42457329596) six matrix failures were expected; Ubuntu Python3.13 1 failed, 5774 passed, 3 skipped. Source `8f7fc69dd443ca3abb6a11c6ed73432a264a87f4` changes the callback owner witness to captured full `Path` equality. No persisted schema, source XY, private dictionary, manual record or real scan was changed.

## Exact-source gates

[CI #42461486965](https://github.com/chigre/PictureCapture/actions/runs/42461486965): Windows/macOS/Ubuntu x Python3.10/3.13 6/6 SUCCESS; Risk tier and Risk-tier CI gate SUCCESS. [OCR #42461486848](https://github.com/chigre/PictureCapture/actions/runs/42461486848): 3/3 SUCCESS. [CodeQL #42461483522](https://github.com/chigre/PictureCapture/actions/runs/42461483522): Analyze Python and Actions 2/2 SUCCESS verified by exact commit Check Runs. Documentation architecture check SKIPPED, not PASS.

## Continuation

Documentation commit is a new SHA and must receive independent exact-head CI/OCR/Risk/CodeQL. Then pursue a genuinely new SECTION/crop-save epoch synthetic RED-first counterexample. No real scans, manual E3/W1–W11/Undo-Redo, real save-reopen, R6 labels or R8 scans; keep sole PR #663 Draft and main untouched.
