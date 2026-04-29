# IMC Prosperity 4 Round 5 Backtester

A small Prosperity 4 backtester trimmed for the Round 5 data in this workspace. It exposes the `prosperity4bt` CLI, builds Prosperity 4-compatible `TradingState` objects, and writes visualizer logs.

## Bundled Data

The default package data is Round 5 only:

- `round 5 day 2`
- `round 5 day 3`
- `round 5 day 4`

The files live in `prosperity4bt/resources/round5`.

## Usage

Run from this repository root:

```sh
.venv/bin/python -m prosperity4bt /Users/robertjahnke/Desktop/prosperity_4/IMC-Prosperity-4/trader.py 5
```

Useful variants:

```sh
# Run one day
.venv/bin/python -m prosperity4bt /path/to/trader.py 5-2

# Use the IMC repo data directory directly
.venv/bin/python -m prosperity4bt /path/to/trader.py 5 --imc-data /Users/robertjahnke/Desktop/prosperity_4/IMC-Prosperity-4/data_root

# Skip writing the visualizer log
.venv/bin/python -m prosperity4bt /path/to/trader.py 5 --no-out
```

By default, output is written to `backtests/darth_trader_visualizer.log`.

## Custom Data Layout

Custom data passed with `--data` should look like:

```text
data_root/
  round5/
    prices_round_5_day_2.csv
    prices_round_5_day_3.csv
    prices_round_5_day_4.csv
    trades_round_5_day_2.csv
    trades_round_5_day_3.csv
    trades_round_5_day_4.csv
```

`--imc-data` also understands the original IMC folder naming, including `ROUND_5`.
