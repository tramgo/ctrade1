# TB15 T03 Fresh Forward Sample

Status: `blocked_no_non_overlapping_forward_slice`

- source detail: `C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1\results\signal_baseline\tb15_cash_secured_put_large_caps_detail.csv`
- source trades: `522`
- source first trade date: `2016-05-09`
- source last expiry date: `2024-07-25`
- local F&O zip count: `2346`
- archive min/max dates: `2015-01-01` / `2024-07-05`
- broker orders allowed: `False`

Inference: the local archive does not contain an options bhavcopy date after the already-used TB15 base sample. A genuine fresh forward sample is therefore not available yet; reusing the original 522 trades would violate the T03 gate.

Next action: refresh local F&O bhavcopy and daily spot data beyond the base sample before rerunning T03. Do not proceed to TB15_T04 defined-risk redesign from this blocked T03 result.
