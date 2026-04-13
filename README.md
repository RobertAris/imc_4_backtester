# IMC Prosperity 4 Backtester

This repository contains a Prosperity 4 oriented fork of the open source Prosperity 3 backtester. It has been adapted to:

- expose a `prosperity4bt` CLI and Python package
- use Prosperity 4 style tutorial data by default
- emit `XIRECS` in generated trade logs
- build Prosperity 4 `Observation` objects with `sunlight` and `humidity`
- tolerate missing or evolving observation columns instead of crashing

## Included Data

The bundled default dataset is the Prosperity 4 tutorial data currently present in this workspace:

- `round 0 day -2`
- `round 0 day -1`

Those files live in [`prosperity4bt/resources/round0`](/Users/robertjahnke/Desktop/prosperity_4/IMC-Prosperity-4/imc_4_backtester/prosperity4bt/resources/round0).

## Usage

```sh
.venv/bin/python -m prosperity4bt /path/to/trader.py 0
```

Run commands from the repository root. Using `python -m prosperity4bt` avoids issues with a stale or missing `prosperity4bt` console script in the virtual environment.
By default, the backtester overwrites `backtests/darth_trader_visualizer.log` on each run. Use `--out /path/to/file.log` if you want a different output file.

Examples:

```sh
# Run both bundled tutorial days
.venv/bin/python -m prosperity4bt /path/to/trader.py 0

# Run a specific tutorial day
.venv/bin/python -m prosperity4bt /path/to/trader.py 0--1

# Use a custom Prosperity 4 data directory
.venv/bin/python -m prosperity4bt /path/to/trader.py 0 --data /path/to/data_root
```

## Data Layout

Custom data passed through `--data` should follow this structure:

```text
data_root/
  round0/
    prices_round_0_day_-2.csv
    prices_round_0_day_-1.csv
    trades_round_0_day_-2.csv
    trades_round_0_day_-1.csv
```

Observation files are optional. If present, place them next to the price/trade files as:

```text
observations_round_<round>_day_<day>.csv
```

The parser accepts both comma and semicolon delimited observation files and understands either camelCase or snake_case field names for the core conversion fields.

## Notes

- Position limits are currently configured for the bundled tutorial products only: `EMERALDS` and `TOMATOES`, both at `80`.
- When later Prosperity 4 rounds introduce more products, update `LIMITS` in [`prosperity4bt/data.py`](/Users/robertjahnke/Desktop/prosperity_4/IMC-Prosperity-4/imc_4_backtester/prosperity4bt/data.py).
- The `--vis` option still opens the existing Prosperity 3 visualizer URL. The log format remains close to the original backtester, but visualizer compatibility may depend on your trader logs.
