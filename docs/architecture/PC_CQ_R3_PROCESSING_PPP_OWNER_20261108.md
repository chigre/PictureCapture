# R3 processing ReviewWindow / PPP independent-save ownership — 2026-11-08

## Reproduced synthetic failure

On test-only commit `c2614631b1266188831a7e532c2c3ef3fb81d1d2`, CI #42409272878 ran all six OS/Python jobs and failed the new synthetic assertion; Ubuntu 3.13: 1 failed, 5770 passed, 3 skipped. The ReviewWindow's visible text differed from its persisted Entry; foreground batch state was `processing`; main autosave's PPP write succeeded. `autosave_commit` returned True before marking `_r3_autosave_unconfirmed`, permitting a generic autosave success status despite uncommitted human text. Existing text and persisted Entry were unchanged, and main PDIC fallback was prohibited. This demonstrates an acknowledgement/status bug, **not** proven on-disk text loss.

## Minimal repair

Commit `5402f4a1695e3ed2899555da776d293e12d38ba7` changes only `review_page_lifecycle.py`: processing early return sets `_r3_autosave_unconfirmed=True` and warns that review text is not saved/confirmed. It still returns True to prohibit competing main-canvas PDIC publication. PPP may be saved independently but cannot mask the unconfirmed review text. Existing retry scheduling remains unchanged. The RED test is unchanged. Source exact-head CI/OCR/CodeQL verification is **pending**, not GREEN at this checkpoint.

## Limits and next gate

Synthetic E2 only; no Windows operator E3 or real dictionary/PDIC/PPP/SECTION/Profile/OCR save/reopen. No cross-file atomicity, rollback, CAS, source XY or schema changes. First verify the live sole Draft PR #663 HEAD and complete six CI matrices, Risk-tier/gate, three OCR smoke jobs and CodeQL Python/Actions on that exact HEAD. Documentation architecture check SKIPPED is not PASS. Continue R4.2 SECTION/crop-save epoch and R5–R7 only with new concrete counterexamples. All user-deferred human/real scans remain NOT PERFORMED/DEFERRED.
