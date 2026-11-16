# PC-CQ R4.2 ordinary ReviewWindow crop source content

- `review_workspace_workflow._request_render_rows()` previously authorized row crops from the captured project, page, geometry, Entry and live text. The actual source image could change after the worker read it while those witnesses stayed equal.
- Crop workers bind the decoded byte snapshot to SHA-256. A second worker on the same generation-managed key streams the current source and verifies digest and handle metadata. The Tk callback revalidates owner and live text, then reopens the current path to check identity and change time immediately before publishing. Windows uses the filesystem change time because its Python `st_ctime_ns` normally records creation time. Unreadable or changed sources use the existing retryable error path, preserving live editors.
- [Exact RED CI](https://github.com/chigre/PictureCapture/actions/runs/43124415532) at `430571adfefe1299cd569177cf01db497c7d4606` gave **4 failed / 5775 passed / 3 skipped** on Ubuntu Python 3.13. The four source tests now execute both worker stages when applicable. Existing project/path/geometry/text tests now use real synthetic worker payloads. The text test also checks a change after verification. The off-Tk contract still requires decoding and resize in the crop worker.
- Local Python 3.13: **4 targeted passed**, **213 related passed**, **5780 full passed / 3 skipped**. Architecture guard, change guard and F821 passed. Acceptance requires the repair commit's exact-head CI, OCR and CodeQL. Source verification is bounded by the final filesystem observation. Manual and real-data acceptance stays deferred.

Adjacent-page prefetch has a separate publication path. Its image key uses size and mtime and a same-path BMP rewrite with those values preserved reproduced stale crop acceptance locally. Follow the adjacent-page prefetch checkpoint after the repair gates complete.

## Exact foreground gates and adjacent prefetch

Foreground source repair [a9c5bb9c](https://github.com/chigre/PictureCapture/commit/a9c5bb9c990ca8ae091f3bd7240e4bdb184b1373) exact [CI](https://github.com/chigre/PictureCapture/actions/runs/43884146847) six matrix and Risk tier/final gate SUCCESS, Ubuntu Python 3.13 **5780 passed / 3 skipped**, [OCR](https://github.com/chigre/PictureCapture/actions/runs/43884147043) 3/3 SUCCESS and [CodeQL](https://github.com/chigre/PictureCapture/actions/runs/43884135175) 2/2 SUCCESS. Documentation architecture SKIPPED.

Adjacent prefetch uses one source metadata witness across request, worker completion and consumption. The handle key observes filesystem file identity, size, modification time and change time. Full foreground source hashing remains in its existing workers. The adjacent-page test exercises a stale and unchanged synthetic BMP. Local RED 1 failed / 1 passed and GREEN 2 targeted / 236 related / 5782 full passed / 3 skipped. Its exact remote gates are pending at this checkpoint.

## Windows metadata counterexample and byte verification

Windows Python 3.13: 1 failed / 5782 passed / 3 skipped (adjacent prefetch). Windows Python 3.10: 1 failed / 5783 passed / 2 skipped (foreground final delivery). Four other matrix jobs and Risk tier succeeded. Risk-tier gate failed. Documentation architecture SKIPPED.

The final foreground callback compares a fresh full digest and file metadata with the background verifier witness. The adjacent prefetch key now includes the full source digest. Both use bounded chunks. These final observations can do file I/O on Tk and do not create filesystem atomicity. The original Windows tests remain, with deterministic equal-metadata variants adding two failures before the source change. The repair exact-head gates must be verified separately.

## Same-path row-height callback ownership

The debounced row-height worker in review_crop_actions.py reads the main window's captured image object. Before mutating any crop/photo/height state, the callback now verifies that the live image is still that object. Synthetic replacement at the same path and unchanged row generation gave local RED 1 failed / 1 positive passed. Local GREEN after rebasing was 53 related and 5786 full passed / 3 skipped.

Exact Windows-content repair 374f4efb008757f7ad63f636a088d1a92e606a0d CI #43887827482 six matrix and Risk tier/gate SUCCESS. Ubuntu 3.13 5785 passed / 3 skipped. OCR #43887827611 3/3 SUCCESS. CodeQL #43887818270 2/2 SUCCESS. Documentation architecture SKIPPED.
