# Thesis Batch 01 Closeout

Date: 2026-03-25

This closeout file records completed decisions within Batch 01 as they happen. The batch is not fully closed yet.

## Completed Decisions

### `TB01_T01` Native15mFailedBreakout
- Research verdict: alive
- Best research candidate: `E1602`
- Best research profile:
  - AUC `0.5750242309686432`
  - balanced accuracy `0.5537999010069146`
  - spread `0.0026510840805298846`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1601_BANDED_70`
- Best executable return: `-5.820192894889364e-05`
- Decision: `research_only`

Reason:
- `E1601` was too sparse to matter.
- `E1602` was the real research candidate but remained clearly negative after costs in executable baseline.

### `TB01_T02` Native15mOpenDrive
- Research verdict: alive
- Best research candidate: `E1702`
- Best research profile:
  - AUC `0.5770899622388297`
  - balanced accuracy `0.5565408256687087`
  - spread `0.0014270931107690785`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1701_BANDED_70`
- Best executable return: `-0.0006190150485907`
- Decision: `research_only`

Reason:
- `E1702` and `E1701` both produced real research signal and real executable activity.
- The branch was not a fake no-trade artifact after the filter fix, but the best executable policy still stayed net negative after costs.

### `TB01_T03` Native15mSessionPhase
- Research verdict: alive
- Best research candidate: `E1803`
- Best research profile:
  - AUC `0.6341835397008408`
  - balanced accuracy `0.6081429351342786`
  - spread `0.0008386969864369726`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1802_BANDED_70`
- Best executable return: `-0.0001341339035688`
- Decision: `research_only`

Reason:
- `E1803` was a very strong classifier in research terms, but still sat in a weak economic slice.
- `E1802` was the least-bad executable candidate, but it still failed to beat `FLAT`.

### `TB01_T04` Native15mHoldingHorizon
- Research verdict: alive
- Best research candidate: `E1903`
- Best research profile:
  - AUC `0.6070648832522949`
  - balanced accuracy `0.5832163359768442`
  - spread `0.0008443445213692815`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E1902_BANDED_70`
- Best executable return: `-0.0016108139104049`
- Decision: `research_only`

Reason:
- Explicit hold-duration matching did change the research profile and `E1902` was the least-bad executable version.
- But horizon selection alone did not repair the economics; the branch traded broadly enough to be meaningful and still stayed clearly below `FLAT`.

### `TB01_T05` Native15mTopKEventRank
- Research verdict: alive
- Best research candidate: `E2003`
- Best research profile:
  - AUC `0.6067849843284833`
  - balanced accuracy `0.582321134878414`
  - spread `0.0010655325554618938`
- Baseline verdict: live-stopped as non-promising
- Best executable read:
  - `E2003` and `E2004` were broadly negative in early live baseline output
  - `E2002_BANDED_*` was mostly flat-to-negative
  - only `E2002_LONGONLY` showed occasional isolated positive slices
- Decision: `research_only`

Reason:
- This branch improved classification quality and matched the new slice-first design rule better than earlier ports.
- But the early executable shape still looked wrong: the main research leaders stayed negative, while only a marginal `LONGONLY` variant showed any life.
- The run was stopped deliberately after enough live evidence to avoid spending more runtime on a branch that was not developing into a real challenger.

### `TB01_T06` Native15mMeanReversionExhaustion
- Research verdict: alive
- Best research candidates:
  - `E2104`
  - `E2102`
- Best research profile:
  - `E2104`
    - AUC `0.6265938631210183`
    - balanced accuracy `0.5980002041979453`
    - spread `0.0006549395917038567`
  - `E2102`
    - AUC `0.6213692738611186`
    - balanced accuracy `0.5884761966566369`
    - spread `0.004453171572029656`
- Baseline verdict: challenger candidate
- Best executable policy:
  - `SIGNAL_E2104_LONGONLY`
  - return `+0.0006684475304197`
  - turnover `0.1552358573075147`
  - trades `6.246913580246914`
- Direct compare read:
  - `SIGNAL_E2104_LONGONLY` beat `FLAT`
  - `SIGNAL_E2104_LONGONLY` beat native-`15m` `SIGNAL_E211_BANDED_68` compare framing, where `E211` was inert
  - row breadth:
    - positive rows `34`
    - zero rows `6`
    - negative rows `41`
  - ticker breadth:
    - positive tickers `15`
    - negative tickers `12`
    - top positive share `0.482287996160751`
- Wider validation read:
  - `SIGNAL_E2104_LONGONLY` widened to `162` rows and turned negative at `-0.0004467734528908`
  - `FLAT` stayed `0.0`
  - native-`15m` `SIGNAL_E211_BANDED_68` remained inert in this framing
  - row breadth weakened:
    - positive rows `52`
    - zero rows `15`
    - negative rows `95`
  - ticker breadth weakened:
    - positive tickers `8`
    - negative tickers `19`
    - top positive share `0.374672210834352`
- Decision: `research_only`

Reason:
- This is the first recent native-`15m` slice-first branch to produce a positive executable baseline with real breadth.
- That first positive compare was useful and worth validating.
- Broader validation then did its job and rejected the branch before overpromotion: the positive signal did not hold up when the coverage widened.

### `TB01_T07` SixtyMinuteDailyContext
- Research verdict: alive
- Best research candidate: `E2201`
- Best research profile:
  - AUC `0.571551488124976`
  - balanced accuracy `0.5577539690068156`
  - spread `0.003482326754324493`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E2201_BANDED_70`
- Best executable return: `-0.0018261473995522`
- Decision: `research_only`

Reason:
- `E2201` was the only daily-context candidate with credible real-vs-shuffled separation and enough sample count to justify executable testing.
- That research quality did not convert to money: every executable `E2201` policy stayed below `FLAT`, and the least-bad banded policy still finished well below the incumbent `SIGNAL_E211_BANDED_68`.
- The branch showed only narrow positive breadth in executable validation, with `2` positive tickers versus `11` negative and a concentrated positive contribution profile.

### `TB01_T08` Native15mBreadthEvent
- Research verdict: alive
- Best research candidate: `E2302`
- Best research profile:
  - AUC `0.5391964901260273`
  - balanced accuracy `0.5270546797374717`
  - spread `0.0007192402278572606`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E2302_BANDED_70`
- Best executable return: `-0.00044532045311487247`
- Decision: `research_only`

Reason:
- `E2302` was a real research survivor with positive real-vs-shuffled separation and enough sample count to justify baseline.
- That research quality still did not monetize: every tested `E2302` / `E2304` executable policy stayed below `FLAT`, and looser bands only deepened the losses.
- The branch therefore remained a useful research artifact rather than an executable challenger, even though the incumbent `SIGNAL_E211_BANDED_68` was inert in this particular baseline frame.

### `TB01_T09` EventConditionedSizingVeto
- Research verdict: alive
- Best research candidate: `E2403`
- Best research profile:
  - incumbent-entry audit spread `0.001316191246583983`
  - kept mean trade pnl `0.0011981066685668035`
  - vetoed mean trade pnl `-0.00011808457801717949`
- Baseline verdict: failed
- Best executable policy: `SIGNAL_E2403_E211_EVENT_CONTEXT_VETO`
- Best executable return: `6.986428963125287e-05`
- Decision: `research_only`

Reason:
- The overlay thesis was economically valid: it only acted inside incumbent `E211` entries, and the `E2403` consensus veto clearly improved the entry-quality audit before execution.
- Executable baseline still failed the promotion gate. `SIGNAL_E2403_E211_EVENT_CONTEXT_VETO` stayed positive after costs and cut drawdown to `9.031270134116682e-05`, but it did not beat the incumbent return of `0.0001012555869542`.
- Executable breadth also became materially sparser, with `3` positive tickers, `21` zero tickers, and `3` negative tickers, so broader validation was not justified.

## Current Next Action

### `TB01_T10` NewDataAxisIfAvailable
- Status: not opened
- Decision: `not_opened_no_new_data`
- Reason: local inspection found only the existing OHLCV-derived, market, sector, breadth, and daily-context stack. That does not satisfy the "materially new local data axis" gate.
- Next step: carry this requirement into Batch 02 as `TB02_T10`, but do not open it until a real local feed exists.

## Batch 01 Final Status

- Closed executable theses: `9 / 10`
- Held data-axis thesis: `1 / 10`
- Promoted challengers: `0`
- Incumbent remains: `SIGNAL_E211_BANDED_68`
- RL status: frozen

Batch 01 succeeded as a research sieve, not as a trading-engine promotion batch. It showed that the stack can detect predictive structure, but price-derived single-name signal families repeatedly failed post-cost executable validation.

The next batch should therefore emphasize cross-sectional/commonality structure, liquidity and volume states, and incumbent-aware execution control before any RL work.

## Batch Status

- Closed / held theses: `10 / 10`
- Active theses: `0`
- Backlog theses: `0`
