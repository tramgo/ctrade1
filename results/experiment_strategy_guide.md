# Experiment Strategy Guide

> Supporting explainer document. For the canonical strategy/program view, use [grand_plan.md](c:/Ramgo/Business/Trading/India2026/Gitrade1/ctrade1/results/grand_plan.md).

## Update 2026-03-27

The guide below is still useful, but the strategic interpretation has now become more explicit.

### Added lesson

The recent native `15m` branches tell us:

- predictive structure is not the same as tradable structure
- relative ranking is not enough by itself
- the best next strategies should isolate favorable events or regimes first, and only then rank opportunities inside them

### Newly completed items since the earlier version

- `Native15mFailedBreakout`
  - research alive
  - baseline failed
- `Native15mOpenDrive`
  - research alive
  - baseline active and broad enough to matter
  - still net negative after costs

### Current active item

- `Native15mSessionPhase`
  - research alive
  - baseline pending

### Current plain-English takeaway

`E211` is still winning not because it is the fanciest classifier, but because it is finding opportunities inside a healthier economic slice than most challengers.

Date: 2026-03-25

## Purpose

This note explains, in plain language, what we have been trying in the signal research program.

The project goal is:

- build a sound intraday trading engine
- profitable after costs
- potentially with or without RL
- with a practical long-term target above `12%` annualized return

The important rule in this project has been:

- first find a signal that works as a simple tradable baseline
- only then consider RL or more advanced execution

So most experiments below are about **signal generation**, not RL.

## How to read this document

Each branch below answers:

1. What was the idea?
2. In layman terms, what signal were we trying to detect?
3. What features did we use?
4. What happened?

## Core benchmark: `E211_Incumbent`

### Idea

This is the best signal family we found on the main `60m` layer.

### Layman explanation

It tries to find stocks that are:

- already moving in a useful direction
- doing so with some persistence
- not completely random or noisy

In simple terms:

> "Find hourly setups that look like real trend/regime opportunities rather than random price movement."

### Main feature style

- trend direction
- persistence
- session context
- price-relative features
- volatility / regime context

### Best tradable expression

- `SIGNAL_E211_BANDED_68`

### Result

- still the best executable benchmark
- positive after costs
- but still not strong enough to call a final deployable engine

## `AblationGrid`

### Idea

Systematically remove or combine feature families and targets to see what actually matters.

### Layman explanation

This is like taking apart the recipe and checking:

- does momentum help?
- does candle shape help?
- does session context help?
- does relative-strength help?

### Main feature style

- combinations of existing `60m` feature families
- multiple target definitions

### Result

- very useful for understanding the research stack
- not a winning tradable branch by itself

## `CrossSectional60m`

### Idea

Instead of asking whether one stock looks good by itself, ask whether it looks better than the other stocks right now.

### Layman explanation

This is a relative-ranking idea:

> "Buy the stronger names compared with the rest of the universe, not just the names that look good in isolation."

### Main feature style

- cross-sectional rank
- relative momentum
- relative mean reversion
- cross-sectional spreads

### Result

- research survived
- executable baseline did not beat the incumbent

## `MarketState60m`

### Idea

The same setup may behave differently in different market states.

### Layman explanation

This branch asks:

- is the market trending?
- calm?
- stressed?
- transitioning?

Then it tries to trade setups differently depending on that state.

### Main feature style

- bull / bear / transition labels
- market volatility pressure
- trend score
- calm vs stress context

### Result

- produced `E801`, the closest `60m` challenger
- still did not beat `E211`

## `SetupRegime`

### Idea

Build setup-specific models instead of one generic score.

### Layman explanation

Rather than saying "one signal fits all," this tries to split the world into types like:

- continuation
- pullback
- carry
- failed breakout

### Main feature style

- setup flags
- regime labels
- relative carry / setup confirmation

### Result

- useful research branch
- no promotable executable winner

## `Multiscale60m`

### Idea

Use several lookback scales together instead of one.

### Layman explanation

A stock may look strong on one horizon and weak on another. This branch tries to compare:

- short trend
- medium trend
- broader trend
- short-term volatility vs longer-term volatility

### Main feature style

- multi-horizon returns
- trend alignment
- range compression / expansion
- volatility ratios

### Result

- strong academic-looking research
- failed executable monetization

## `SecondTimeframe60m`

### Idea

Keep trading on hourly bars, but add real `15m` context inside each hour.

### Layman explanation

This asks:

> "Inside the hour, was the move smooth and healthy, or messy and unstable?"

The hourly signal stays the main driver, but lower-timeframe information is added as extra context.

### Main feature style

- `15m -> 60m` aggregation
- intrahour drift quality
- path efficiency
- rejection / failure signs
- late-strength vs early exhaustion

### Result

- improved research quality
- did not beat `E211` in baseline execution

## `IntrahourPathV1`

### Idea

Use the internal path of the hour as a source of information.

### Layman explanation

Two hourly candles can look identical at the end, but one may have:

- risen smoothly

while another may have:

- spiked up
- fallen back
- recovered messily

This branch tried to tell those apart.

### Main feature style

- path efficiency
- positive / negative share of the `15m` bars
- sign-flip rate
- max adverse excursion
- high-before-low / low-before-high
- rejection score
- failed-breakout score

### Result

- good research quality
- poor baseline tradability

## `TimeDistributionV2`

### Idea

When the move happens inside the hour may matter as much as how large the move is.

### Layman explanation

This branch asks:

- did the move happen early and fade?
- or late and accelerate?

That can distinguish:

- exhaustion
- continuation

### Main feature style

- first-half vs second-half return
- late-strength share
- time imbalance
- early vs late volatility
- last-quarter return
- early exhaustion score

### Result

- `E1401` looked slightly better than `E211` in research metrics
- still failed executable baseline

## `BreadthContext60m`

### Idea

Use universe-wide participation rather than just stock-specific signals.

### Layman explanation

This asks:

- are many stocks participating in the move?
- are only a few leading?
- is the market broad and healthy or narrow and fragile?

### Main feature style

- advancing fraction
- leader fraction
- laggard fraction
- breadth trend pressure
- breadth dispersion
- participation / expansion features

### Result

- real research structure
- baseline still negative

## `PortfolioRank60m`

### Idea

Instead of trading one stock independently, rank the whole universe and build a portfolio.

### Layman explanation

This is:

- long the best names
- short the worst names
- rebalance as rankings change

### Main feature style

- cross-sectional portfolio ranking
- top vs bottom selection
- portfolio turnover and concentration analysis

### Result

- valid and important test
- high turnover and weak performance

## `E211 + Intrahour Veto`

### Idea

Do not replace `E211`. Only block trades when intrahour quality looks bad.

### Layman explanation

This is a filter idea:

> "Keep the benchmark, but skip it when the lower-timeframe action looks unstable."

### Main feature style

- rejection score
- sign-flip rate
- weak path efficiency
- weak late strength
- early exhaustion

### Result

- first veto version was effectively a no-op
- did not change actual benchmark behavior

## `Native15mExecution`

### Idea

If some signal decays too fast for hourly execution, test it directly on `15m`.

### Layman explanation

This stopped compressing fast information back into hourly bars and instead asked:

> "Can we trade directly on `15m` signals at the timescale where the information lives?"

### Main feature style

- recent `15m` return path
- path efficiency
- sign-flip rate
- time imbalance
- early exhaustion
- rejection score
- close location
- breakout/body pressure
- short-vs-long volatility ratio

### Main families

- `E1501` `Direct15mContinuation`
- `E1502` `Direct15mCandlePath`
- `E1503` `Direct15mRelativeBarrier`
- `E1504` `Direct15mStateAwareBarrier`

### Result

- research was clearly alive
- `E1501` led on research
- `E1502` had a very sparse initial positive blip
- broader validation turned that positive blip negative
- native-`15m` `E211` and `E102` were inert in executable comparison
- native-`15m` `E1301` traded, but still lost money

### Conclusion

Native `15m` is not dead, but the ranking/classifier families tested so far have not produced a durable tradable winner.

## `All15m` Broad Research Sweep

### Idea

Run many of the main experiment families directly on native `15m` bars.

### Layman explanation

This is the broad screening pass:

> "Which families still look alive when moved to `15m`?"

### Main result

The sweep showed that `15m` research is definitely alive.

Important survivors included:

- `E1301`
- `E102`
- `E1501`
- `E211`

But when actually baseline-tested:

- `E102` was inert
- `E1301` was active but negative
- `E1501` was negative
- native-`15m` `E211` was inert

So the broad sweep helped rank ideas, but did not yet produce a winning executable branch.

## `Native15mFailedBreakout`

### Idea

Move away from continuous ranking models and test **event-driven** `15m` setups.

### Layman explanation

Instead of scoring every bar, this branch only cares about specific local events like:

- price pushes through a level
- fails to hold it
- shows rejection
- closes weakly or reverses

This is much closer to how many short-term traders think about `15m` charts.

### Main feature style

- rejection score
- close location in recent range
- breakout pressure
- candle body pressure
- sign-flip rate
- time imbalance
- early exhaustion
- short-vs-long volatility ratio

### Main families

- `E1601` `FailedUpsideBreakout`
- `E1602` `SessionAwareBreakoutFailure`
- `E1603` `RelativeFailedBreakout`
- `E1604` `StateAwareBreakoutFailure`

### Current status

- implementation complete
- research has started to look promising
- `E1602` appears to be the early research leader
- baseline verdict still pending at the time of writing

## Cost model work

We also audited whether the cost model itself was the main problem.

### Layman explanation

We tested whether weak strategies only looked weak because trading costs were too harsh.

### What we checked

- realistic costs
- half slippage
- fees-only
- frictionless

### Conclusion

Costs matter, but they did **not** explain away the failures.

In simple terms:

- good strategies stayed better
- bad strategies stayed bad

## What we think we learned so far

### Things achieved

- the research stack can find real predictive structure
- the system can reject weak branches consistently
- `E211` is reproducible and remains the best benchmark
- native `15m` contains real information
- not all predictive improvements are monetizable improvements

### Things still missing

- no branch has yet produced a clearly durable, post-cost engine strong enough for the final project objective
- native `15m` has not yet produced a validated winner
- RL still does not have a justified promotion candidate

## Plain-English bottom line

So far, the project has shown:

- we **can** discover real signal
- we **can** test it honestly
- many ideas look interesting in research
- but most of them do not survive real trading constraints

The current benchmark is still:

- `SIGNAL_E211_BANDED_68`

The current frontier is:

- native `15m`
- event-driven intraday logic
- especially failed-breakout / rejection behavior

That is why the next high-value work is focused there.
