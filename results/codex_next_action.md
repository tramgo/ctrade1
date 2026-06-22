# Codex Next Action

## Current Status

- Active batch: `TB11`
- Last completed thesis: `TB11_T11_ConditionalOverlayFrontier`
- Last verdict: `balanced_candidate_needs_lot_capital_risk_calibration`
- Best growth candidate: `TB11_T06_liq60k_ret5_0p01`
- Best defensive candidate: `TB11_T08_dte8_ret5_0p02`
- Best balanced overlay: `def_full_resg50_ovg50`
- Equity incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen
- Run lock: unlocked

## TB11 Real-Chain Tail-Control Result

`TB11` reopened options research only under the rule set by `TB10`: real-chain-first, direct tail-control focus, no synthetic evidence for promotion.

Commands executed:

```powershell
python -u -B ssell1.py --mode signal_baseline_tb11_options_tail_control_sweep
python -u -B ssell1.py --mode signal_baseline_tb11_options_spot_regime_tail_sweep
```

Artifacts:

- `results/signal_baseline/tb11_options_tail_control_detail.csv`
- `results/signal_baseline/tb11_options_tail_control_summary.csv`
- `results/signal_baseline/tb11_options_tail_control_metadata.csv`
- `results/signal_baseline/tb11_options_tail_control_skipped.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_detail.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_summary.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_metadata.csv`
- `results/signal_baseline/tb11_options_spot_regime_tail_skipped.csv`

Best first-pass tail-control variant:

- strategy: `TB11_farther_3pct_vix_shock_skip`
- trades: `864`
- annualized return on estimated margin: `10.18%`
- worst trade: `-611.03` points
- max drawdown: `-3650.11` points

Best spot-regime variant:

- strategy: `TB11_spot_3pct_ret5_m1_sma_0`
- trades: `498`
- annualized return on estimated margin: `18.19%`
- worst trade: `-611.03` points
- max drawdown: `-1390.71` points
- win rate: `76.10%`

Important caveats:

- the worst loss remains the `2022-06-08` to `2022-06-16` trade
- `2024` contribution is large enough to require concentration review
- the candidate is not deployable before robustness and tail audit

## Verdict

`TB11_spot_3pct_ret5_m1_sma_0` is research-interesting, but `TB11_T03` blocks promotion.

Audit evidence:

- all-period annualized return on estimated margin: `18.19%`
- pre-2024 annualized return on estimated margin: `16.60%`
- 2024 annualized return on estimated margin: `199.33%`
- 2024 PnL share: `41.14%`
- fold 2 point PnL: `-7.42`
- worst loss cluster remains in `2020`, `2021`, and `2022`
- excluding only the worst 2022 trade still leaves max drawdown at `-1390.71` points

## T04 Result

Do not run another broad options sweep.

`TB11_T04 LossClusterMaxRiskControl` has now found a better-shaped candidate:

- strategy: `TB11_T04_3pct_5wing_ret5_1pct_liq50k`
- trades: `157`
- annualized return on estimated margin: `24.92%`
- worst trade: `-270.89` points
- max drawdown: `-274.28` points
- win rate: `88.54%`
- 2024 PnL share: `9.24%`
- all calendar years and all chronological folds are positive

## Next Action

`TB11_T05` through `TB11_T09` are now complete.

`TB11_T05` showed the return/loss frontier:

- `50k` liquidity kept high return but retained a `-270.89` point worst trade
- `75k` and `100k` liquidity cut worst trade to about `-68.50` but reduced return

`TB11_T06` found the best current frontier point:

- strategy: `TB11_T06_liq60k_ret5_0p01`
- trades: `141`
- annualized return on estimated margin: `24.38%`
- worst trade: `-69.21` points
- max drawdown: `-69.21` points
- win rate: `89.36%`
- all calendar years and all chronological folds are positive

## Current Frontier

Growth candidate:

- `TB11_T06_liq60k_ret5_0p01`
- base annualized return on estimated margin: `24.38%`
- base worst trade / max DD: `-69.21`
- harshest tested annualized return: `11.77%` under `30%` premium haircut and `3` points per leg
- harshest tested worst trade / max DD: `-86.61` / `-142.84`

Defensive candidate:

- `TB11_T08_dte8_ret5_0p02`
- base annualized return on estimated margin: `17.57%`
- base worst trade / max DD: `-1.25`
- harshest tested annualized return: `9.11%` under `30%` premium haircut and `3` points per leg
- harshest tested worst trade / max DD: `-10.36` / `-18.77`

## Next Action

`TB11_T10` and `TB11_T11` are now complete.

Static allocation mostly just scaled exposure down. Conditional overlay created a better balanced frontier.

Best max-return overlay:

- allocation: `def_full_resg100_ovg50`
- base annualized return: `27.21%`
- base worst / max DD: `-69.21` / `-69.20`
- harsh-stress annualized return: `14.12%`
- harsh-stress worst / max DD: `-86.61` / `-152.79`

Best balanced overlay:

- allocation: `def_full_resg50_ovg50`
- base annualized return: `24.00%`
- base worst / max DD: `-34.60` / `-34.60`
- harsh-stress annualized return: `12.66%`
- harsh-stress worst / max DD: `-43.30` / `-91.32`
- all chronological folds are positive in base, moderate, and harsh scenarios

## Next Action

Open `TB11_T12_LotCapitalRiskCalibration`.

Required checks:

- convert points to rupees using NIFTY lot size assumptions
- estimate capital requirement from margin points and lot count
- cap position size so worst trade and harsh-stress drawdown fit a defined rupee loss budget
- compare max-return overlay versus balanced overlay after lot/capital constraints
- do not promote, RL-tune, or route to broker execution until allocation sizing passes
