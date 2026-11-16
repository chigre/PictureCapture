# PC-CQ R3 ordinary ReviewWindow uncertain autosave

The ordinary ReviewWindow lifecycle owns the autosave acknowledgement, while the PDIC write guard owns the existing uncertainty flag. A post-write error can leave matching application and editor words while PDIC publication still needs reconciliation. The subsequent clean-text branch previously cleared the ReviewWindow flag and allowed a separate PPP update to present general autosave success.

The ordinary autosave entrypoint now checks the existing uncertainty flag before bridging or comparing editor words. It retains the warning and existing ownership return value. The shared autosave tick can save PPP and re-arm while preserving the unconfirmed ReviewWindow status.

`tests/test_r3_autosave_exception_unconfirmed_20261105.py` exercises the real main autosave tick with matching synthetic Entry/editor values, uncertainty and successful PPP. RED on `d2b207c0decfbf2a0dafbeaddd14f4f6a66be382` was **1 intended failure / 4 passing controls**. Local GREEN was **5 targeted / 38 related / 5783 full passed / 3 skipped**. Exact remote checks are required for the repair. Manual and real-data acceptance remain deferred.
