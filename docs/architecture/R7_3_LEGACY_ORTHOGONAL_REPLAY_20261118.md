# R7.3 legacy orthogonal replay metadata

The read-only coordinate mapper used `int()` for legacy orthogonal grid dimensions, accepting fractions and numeric strings. It also treated boolean gains as numbers and let an empty mapping of modern steps fall through to legacy metadata. A truthy scalar step collection could raise a generic `TypeError` instead of the mapping contract's `CoordinateMappingUnavailable`.

Both modern and legacy replay now use the same nonnegative integer dimension check. The mapper requires a list or tuple of modern step records and rejects boolean legacy gains. Valid empty step sequences still select the legacy fallback. Legacy zero gain remains zero, and the modern decoder retains its existing defaulting policy.

## Evidence

- [RED tests](https://github.com/chigre/PictureCapture/commit/8a8d3d8cdc7e10b38c3710189c6a90380f060cf7) on `e73553fe2023a43627e52f8c66dd90c5751dbff3` produced **6 failed / 11 passed** in the orthogonal payload file. [Source repair](https://github.com/chigre/PictureCapture/commit/6e2c02483d99d997318a779e92921fc6a367a984) passed all **17** in that file and **170** related tests. The final local full suite exercised **5817 passed / 3 skipped**.
- At that checkpoint, the read-only map rejected those inputs. The saved analysis decoder still needed coverage because it could coerce fields or drop invalid step elements before the mapper received them.

## Saved analysis and image export

Cache loading, raster export and coordinate mapping now validate the same saved orthogonal stage sequence. Invalid records, missing passes and non-finite geometry invalidate the cache. The export preparation workflow can rebuild that cache from the source page. A malformed in-memory sequence is rejected before image replay starts. The regression suite exercises the persisted repair path and checks agreement between a reopened two-pass coordinate map and PNG pixels.

The same paths require exact integer crop bounds. Preview and image export check those bounds against the actual corrected raster, including UVDoc output whose dimensions can differ from the source. A refused crop leaves the source and any earlier output intact.

## CI follow-up for R3 and R4.2

- On the previous checkpoint, macOS Python 3.13 passed pytest but [the native focused smoke](https://github.com/chigre/PictureCapture/actions/runs/44261238290/job/134654878715) produced a PDIC conflict. The smoke created `ReviewWindow(app)` directly and left the normal `app.review_window` owner unregistered. A main autosave tick could therefore dispatch its ordinary canvas writer during the synthetic focused save. The [fixture repair](https://github.com/chigre/PictureCapture/commit/a5cb2fe072acd6a51b7f428d36e6aa27fe813adb) uses `app.open_review()` and deliberately fires the main autosave after the first publication and before callback delivery, checking exact PDIC bytes and both expected focused writes.
- [Windows Python 3.10](https://github.com/chigre/PictureCapture/actions/runs/44261238290/job/134654878671) reported 5809 passes and one Tcl initialization error before a focused test could run. The focused unit fixture now reuses a module-local Tcl interpreter with fresh variables and trace cleanup for every case. Local focused save and geometry scalar tests passed **26** cases. Native GUI and platform results require the final HEAD workflows.
- A subsequent [Ubuntu native smoke](https://github.com/chigre/PictureCapture/actions/runs/44262294562/job/134658364893) reached the real registered review, then failed a combined no-change check while background main/settings timer activity was still possible. The final fixture settles the review-open settings callback, takes a canonical PPP baseline and pulses the main autosave only in the gated interleaving. It keeps separate byte-exact assertions for PPP, settings, SECTION and both images. The same intermediate run passed the macOS native smoke.
