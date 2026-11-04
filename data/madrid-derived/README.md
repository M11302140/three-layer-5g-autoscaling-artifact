# Traces derived from the IMDEA Madrid LTE dataset

Files: `madrid_lib.json`, `madrid_compressed.json`, `madrid_compressed_lib.json`, `madrid_1to1.json`, `madrid_1to1_stride30.json`, `madrid_s10_lib.json`, `madrid_s10_1to1.json`. They are per-minute UE-count traces produced from the per-cell RRC-connected user series of the dataset by the scripts in `../../registrations-and-reports/madrid/` (`mad_build.py`, `mad_build_s10.py`, `mad_t12.py`, `mad_t12_s10.py`); the feature tables and the transfer analysis are in the same directory and in the report chapter on Madrid.

Source dataset: the Madrid LTE dataset of Pablo Fernández Pérez, Claudio Fiandrino and Joerg Widmer, IMDEA Networks Institute, https://git2.networks.imdea.org/wng/madrid-lte-dataset (data files via the download link given there). The JSON files in this directory are derived works of that dataset (per-minute UE-count traces computed from its per-cell series), not copies of it; they are redistributed under the same licence, GPL-3.0, with the citation below, as the dataset's licence requires. Licence of the source: GNU General Public License v3.0 (`LICENSE` in this directory is a verbatim copy of the licence file shipped with the dataset). The source data files themselves (`users_*.csv`) are not redistributed here.

Licence of the derived traces: GPL-3.0, the same as the source.

Citation required by the dataset authors:

> P. Fernández Pérez, C. Fiandrino and J. Widmer, "Characterizing and Modeling Mobile Networks User Traffic at Millisecond Level", in Proc. 17th ACM Workshop on Wireless Network Testbeds, Experimental Evaluation & Characterization (WiNTECH '23), Madrid, Spain, 2023, pp. 64–71. doi: 10.1145/3615453.3616509.

BibTeX: `../../registrations-and-reports/madrid/bibtex.txt`.
