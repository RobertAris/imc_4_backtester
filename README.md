# IMC Prosperity 4 Round 3 Backtester

A small Prosperity 4 backtester trimmed for the Round 3 data in this workspace. It exposes the `prosperity4bt` CLI, builds Prosperity 4-compatible `TradingState` objects, writes visualizer logs, and enforces the Round 3 position limits.

## Bundled Data

The default package data is Round 3 only:

- `round 3 day 0`
- `round 3 day 1`
- `round 3 day 2`

The files live in `prosperity4bt/resources/round3`.

## Usage

Run from this repository root:

```sh
.venv/bin/python -m prosperity4bt /Users/robertjahnke/Desktop/prosperity_4/IMC-Prosperity-4/trader_round3.py 3
```

Useful variants:

```sh
# Run one day
.venv/bin/python -m prosperity4bt /path/to/trader_round3.py 3-0

# Use the IMC repo data directory directly
.venv/bin/python -m prosperity4bt /path/to/trader_round3.py 3 --imc-data /Users/robertjahnke/Desktop/prosperity_4/IMC-Prosperity-4/data_root

# Skip writing the visualizer log
.venv/bin/python -m prosperity4bt /path/to/trader_round3.py 3 --no-out
```

By default, output is written to `backtests/darth_trader_visualizer.log`.

## Round 3 Products

Position limits are configured for:

- `HYDROGEL_PACK`: 200
- `VELVETFRUIT_EXTRACT`: 200
- `VEV_4000`, `VEV_4500`, `VEV_5000`, `VEV_5100`, `VEV_5200`, `VEV_5300`, `VEV_5400`, `VEV_5500`, `VEV_6000`, `VEV_6500`: 300 each

## Custom Data Layout

Custom data passed with `--data` should look like:

```text
data_root/
  round3/
    prices_round_3_day_0.csv
    prices_round_3_day_1.csv
    prices_round_3_day_2.csv
    trades_round_3_day_0.csv
    trades_round_3_day_1.csv
    trades_round_3_day_2.csv
```

`--imc-data` also understands the original IMC folder naming, including `ROUND_3`.
