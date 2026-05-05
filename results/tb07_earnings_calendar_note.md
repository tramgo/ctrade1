# TB07 Earnings Calendar Note

- Zerodha does not provide a historical or forward earnings calendar feed through the candle/instrument path used in this repo.
- `data/earnings_calendar.csv` must be populated from a non-Zerodha source or manual process.
- Expected columns: `Date`, `Ticker`, `EventDate`.
- `Date` can be the file/import date; `EventDate` is the actual earnings announcement date used by the strategy filter.
