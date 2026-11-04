# raw-runs/

The per-run raw output (10,706 files, 659 MB uncompressed) is not in the git repository. It is attached to the GitHub release of this record as `raw-runs.tar.zst` (zstd-compressed tar of this directory, including `RUN_INDEX.csv`); its SHA-256 is in `ARCHIVES.sha256` next to it. Unpack with `tar --zstd -xf raw-runs.tar.zst` in the record root; the files then match `SHA256SUMS`.

`RUN_INDEX.csv` (kept in the repository) is the status of every run id: trace, arm, block, status (valid / voided / harness-fault / trial / not-used), reason, replacing run id, whether raw files exist, and the source ledger of the row.
