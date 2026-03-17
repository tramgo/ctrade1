## Current Layer Decision Memo

Date: 2026-03-17

### Decision

The current `60m` signal-discovery layer is now explored enough for this cycle.

We are freezing:

- `SIGNAL_E211_BANDED_68` as the incumbent benchmark
- all recent challenger branches as `research_only`
- RL promotion for new branches on this information layer

We are pausing:

- nearby `60m` feature-variant branch creation
- RL rescue attempts for challenger branches
- threshold / reward / PPO tuning as a path to create alpha

### Why

Across multiple distinct theses, the pattern stayed consistent:

- research metrics often showed real structure
- baseline monetization did not beat the incumbent benchmark

Branch summary:

- `E211_Incumbent`
  - best baseline: `SIGNAL_E211_BANDED_68`
  - return: `+0.0001013`
- `MarketState60m`
  - best baseline: `SIGNAL_E801_BANDED_70`
  - return: `+0.0000655`
- `CrossSectional60m`
  - best baseline: `SIGNAL_E501_BANDED_64`
  - return: `-0.0000530`
- `Multiscale60m`
  - best baseline: `SIGNAL_E906_LONGONLY`
  - return: `-0.0001367`
- `SetupRegime`
  - best baseline: `SIGNAL_E703_BANDED_66`
  - return: `-0.0005880`
- `AblationGrid`
  - best baseline: `SIGNAL_E605_BANDED_70`
  - return: `-0.0025437`

### Practical conclusion

This means the current `60m` OHLCV-derived research layer is productive for understanding signal structure, but not for generating a stronger executable post-cost branch than `E211`.

### Allowed next moves

Only reopen active discovery if the next thesis is materially different from the current layer. Preferred options:

1. Portfolio-level cross-sectional ranking, not per-ticker classification.
2. Richer regime/state engine beyond the current labels.
3. True second-timeframe input, not only derived multi-scale features.

### Not allowed next moves

- another nearby `60m` setup family sweep
- RL promotion without baseline superiority
- branch-local threshold rescue work
- PPO / reward tuning as a substitute for signal quality

### Operating rule going forward

Until a new branch beats `SIGNAL_E211_BANDED_68` in baseline execution:

- keep `E211` as benchmark
- keep challengers as research artifacts
- keep RL out of scope

