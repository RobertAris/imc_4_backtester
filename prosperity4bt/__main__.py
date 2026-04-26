import sys
import uuid
from collections import defaultdict
from functools import reduce
from importlib import import_module, metadata, reload
from pathlib import Path
from typing import Annotated, Any, Optional

import orjson
from typer import Argument, Option, Typer

from prosperity4bt.data import has_day_data
from prosperity4bt.file_reader import FileReader, FileSystemReader, ImcDataReader, PackageResourcesReader
from prosperity4bt.models import BacktestResult, TradeMatchingMode
from prosperity4bt.open import open_visualizer
from prosperity4bt.runner import run_backtest


def parse_algorithm(algorithm: Path) -> Any:
    sys.path.append(str(algorithm.parent))
    return import_module(algorithm.stem)


def parse_data(data_root: Optional[Path], imc_data_root: Optional[Path]) -> FileReader:
    if data_root is not None and imc_data_root is not None:
        print("Error: --data and --imc-data are mutually exclusive")
        sys.exit(1)

    if imc_data_root is not None:
        return ImcDataReader(imc_data_root)

    if data_root is not None:
        return FileSystemReader(data_root)
    return PackageResourcesReader()


def parse_days(file_reader: FileReader, days: list[str]) -> list[tuple[int, int]]:
    parsed_days = []

    for arg in days:
        if "-" in arg:
            round_num, day_num = map(int, arg.split("-", 1))

            if not has_day_data(file_reader, round_num, day_num):
                print(f"Warning: no data found for round {round_num} day {day_num}")
                continue

            parsed_days.append((round_num, day_num))
        else:
            round_num = int(arg)

            parsed_days_in_round = []
            for day_num in range(-5, 100):
                if has_day_data(file_reader, round_num, day_num):
                    parsed_days_in_round.append((round_num, day_num))

            if len(parsed_days_in_round) == 0:
                print(f"Warning: no data found for round {round_num}")
                continue

            parsed_days.extend(parsed_days_in_round)

    if len(parsed_days) == 0:
        print("Error: did not find data for any requested round/day")
        sys.exit(1)

    return parsed_days


def parse_out(out: Optional[Path], no_out: bool) -> Optional[Path]:
    if out is not None:
        return out

    if no_out:
        return None

    return Path.cwd() / "backtests" / "darth_trader_visualizer.log"


def print_day_summary(result: BacktestResult) -> None:
    last_timestamp = result.activity_logs[-1].timestamp

    product_lines = []
    total_profit = 0

    for row in reversed(result.activity_logs):
        if row.timestamp != last_timestamp:
            break

        product = row.columns[2]
        profit = row.columns[-1]

        product_lines.append(f"{product}: {profit:,.0f}")
        total_profit += profit

    print(*reversed(product_lines), sep="\n")
    print(f"Total profit: {total_profit:,.0f}")


def merge_results(
    a: BacktestResult, b: BacktestResult, merge_profit_loss: bool, merge_timestamps: bool
) -> BacktestResult:
    sandbox_logs = a.sandbox_logs[:]
    activity_logs = a.activity_logs[:]
    trades = a.trades[:]

    if merge_timestamps:
        a_last_timestamp = a.activity_logs[-1].timestamp
        timestamp_offset = a_last_timestamp + 100
    else:
        timestamp_offset = 0

    sandbox_logs.extend([row.with_offset(timestamp_offset) for row in b.sandbox_logs])
    trades.extend([row.with_offset(timestamp_offset) for row in b.trades])

    if merge_profit_loss:
        profit_loss_offsets = defaultdict(float)
        for row in reversed(a.activity_logs):
            if row.timestamp != a_last_timestamp:
                break

            profit_loss_offsets[row.columns[2]] = row.columns[-1]

        activity_logs.extend(
            [row.with_offset(timestamp_offset, profit_loss_offsets[row.columns[2]]) for row in b.activity_logs]
        )
    else:
        activity_logs.extend([row.with_offset(timestamp_offset, 0) for row in b.activity_logs])

    return BacktestResult(a.round_num, a.day_num, sandbox_logs, activity_logs, trades)


def write_output_legacy(output_file: Path, merged_results: BacktestResult) -> None:
    """Emit the original plain-text format with three labeled sections.

    Kept for backward compatibility; selectable with --legacy-format.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w+", encoding="utf-8") as file:
        file.write("Sandbox logs:\n")
        for row in merged_results.sandbox_logs:
            file.write(str(row))

        file.write("\n\n\nActivities log:\n")
        file.write(
            "day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;mid_price;profit_and_loss\n"
        )
        file.write("\n".join(map(str, merged_results.activity_logs)))

        file.write("\n\n\n\n\nTrade History:\n")
        file.write("[\n")
        file.write(",\n".join(map(str, merged_results.trades)))
        file.write("]")


# Header for the activitiesLog string field.
_ACTIVITIES_HEADER = (
    "day;timestamp;product;"
    "bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;bid_price_3;bid_volume_3;"
    "ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;ask_price_3;ask_volume_3;"
    "mid_price;profit_and_loss"
)


def _build_activities_log(merged_results: BacktestResult) -> str:
    """Build the activitiesLog string: header + one row per ActivityLogRow,
    joined by '\\n', with a trailing newline (matches submission-server output).
    """
    rows = [_ACTIVITIES_HEADER]
    rows.extend(str(row) for row in merged_results.activity_logs)
    # Target log ends activitiesLog with a trailing '\n' after the last row.
    return "\n".join(rows) + "\n"


def _build_logs_array(merged_results: BacktestResult) -> list[dict[str, Any]]:
    """Build the `logs` array: one object per timestamp."""
    return [
        {
            "sandboxLog": row.sandbox_log,
            "lambdaLog": row.lambda_log,
            "timestamp": row.timestamp,
        }
        for row in merged_results.sandbox_logs
    ]


def _build_trade_history(merged_results: BacktestResult) -> list[dict[str, Any]]:
    """Build the `tradeHistory` array.

    Matches the submission-server schema: price is a float, quantity is an int,
    currency is the string "XIRECS", missing counterparty side is empty string.
    """
    history = []
    for row in merged_results.trades:
        trade = row.trade
        history.append(
            {
                "timestamp": trade.timestamp,
                "buyer": trade.buyer if trade.buyer is not None else "",
                "seller": trade.seller if trade.seller is not None else "",
                "symbol": trade.symbol,
                "currency": "XIRECS",
                # Server emits price as a float, qty as an int.
                "price": float(trade.price),
                "quantity": int(trade.quantity),
            }
        )
    return history


def write_output(output_file: Path, merged_results: BacktestResult) -> None:
    """Emit the visualizer-compatible single-line JSON format.

    Top-level schema:
        {
            "submissionId": "<uuid>",
            "activitiesLog": "<csv string with newlines>",
            "logs": [{"sandboxLog": ..., "lambdaLog": ..., "timestamp": ...}, ...],
            "tradeHistory": [{...trade...}, ...]
        }

    This matches the format produced by the IMC submission server and is
    the format the Prosperity visualizer consumes when given a backtest log.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        # The server uses a real submission UUID; locally we generate a random
        # one so each backtest run is uniquely identifiable.
        "submissionId": str(uuid.uuid4()),
        "activitiesLog": _build_activities_log(merged_results),
        "logs": _build_logs_array(merged_results),
        "tradeHistory": _build_trade_history(merged_results),
    }

    # Single-line JSON, no indentation, matching the server's output format.
    # orjson is already a dependency (used by SandboxLogRow.__str__) and is
    # fast enough for multi-million-row backtests.
    output_file.write_bytes(orjson.dumps(payload))


def print_overall_summary(results: list[BacktestResult]) -> None:
    print("Profit summary:")

    total_profit = 0
    for result in results:
        last_timestamp = result.activity_logs[-1].timestamp

        profit = 0
        for row in reversed(result.activity_logs):
            if row.timestamp != last_timestamp:
                break

            profit += row.columns[-1]

        print(f"Round {result.round_num} day {result.day_num}: {profit:,.0f}")
        total_profit += profit

    print(f"Total profit: {total_profit:,.0f}")


def format_path(path: Path) -> str:
    cwd = Path.cwd()
    if path.is_relative_to(cwd):
        return str(path.relative_to(cwd))
    return str(path)


def version_callback(value: bool) -> None:
    if value:
        print(f"prosperity4bt {metadata.version(__package__)}")
        sys.exit(0)


app = Typer(context_settings={"help_option_names": ["--help", "-h"]})


@app.command()
def cli(
    algorithm: Annotated[Path, Argument(help="Path to the Python file containing the algorithm to backtest.", show_default=False, exists=True, file_okay=True, dir_okay=False, resolve_path=True)],
    days: Annotated[list[str], Argument(help="The days to backtest on. <round>-<day> for a single day, <round> for all days in a round.", show_default=False)],
    merge_pnl: Annotated[bool, Option("--merge-pnl", help="Merge profit and loss across days. Visualizer-compatible JSON output enables this automatically.")] = False,
    vis: Annotated[bool, Option("--vis", help="Open backtest results in the browser visualizer when done.")] = False,
    out: Annotated[Optional[Path], Option(help="File to save output log to (defaults to backtests/darth_trader_visualizer.log).", show_default=False, dir_okay=False, resolve_path=True)] = None,
    no_out: Annotated[bool, Option("--no-out", help="Skip saving output log.")] = False,
    data: Annotated[Optional[Path], Option(help="Path to data directory. Must look similar in structure to prosperity4bt/resources.", show_default=False, exists=True, file_okay=False, dir_okay=True, resolve_path=True)] = None,
    imc_data: Annotated[Optional[Path], Option("--imc-data", help="Path to the IMC repo DATA directory. Supports IMC folder names like ROUND_2 and flat augmented price files like price_round_2_day_1_augmented.csv.", show_default=False, exists=True, file_okay=False, dir_okay=True, resolve_path=True)] = None,
    print_output: Annotated[bool, Option("--print", help="Print the trader's output to stdout while it's running.")] = False,
    match_trades: Annotated[TradeMatchingMode, Option(help="How to match orders against market trades. 'imc' uses a stricter IMC-style approximation, 'all' matches trades with prices equal to or worse than your quotes, 'worse' matches trades with prices worse than your quotes, 'none' does not match trades against orders at all.")] = TradeMatchingMode.imc,
    no_progress: Annotated[bool, Option("--no-progress", help="Don't show progress bars.")] = False,
    original_timestamps: Annotated[bool, Option("--original-timestamps", help="Preserve original timestamps in output log rather than making them increase across days.")] = False,
    legacy_format: Annotated[bool, Option("--legacy-format", help="Write the old plain-text three-section log format instead of the visualizer-compatible JSON format.")] = False,
    version: Annotated[bool, Option("--version", "-v", help="Show the program's version number and exit.", is_eager=True, callback=version_callback)] = False,
) -> None:  # fmt: skip
    if out is not None and no_out:
        print("Error: --out and --no-out are mutually exclusive")
        sys.exit(1)

    try:
        trader_module = parse_algorithm(algorithm)
    except ModuleNotFoundError as e:
        print(f"{algorithm} is not a valid algorithm file: {e}")
        sys.exit(1)

    if not hasattr(trader_module, "Trader"):
        print(f"{algorithm} does not expose a Trader class")
        sys.exit(1)

    file_reader = parse_data(data, imc_data)
    parsed_days = parse_days(file_reader, days)
    output_file = parse_out(out, no_out)

    show_progress_bars = not no_progress and not print_output

    results = []
    for round_num, day_num in parsed_days:
        print(f"Backtesting {algorithm} on round {round_num} day {day_num}")

        reload(trader_module)

        result = run_backtest(
            trader_module.Trader(),
            file_reader,
            round_num,
            day_num,
            print_output,
            match_trades,
            True,
            show_progress_bars,
        )

        print_day_summary(result)
        if len(parsed_days) > 1:
            print()

        results.append(result)

    if len(parsed_days) > 1:
        print_overall_summary(results)

    if output_file is not None:
        merge_output_pnl = merge_pnl or not legacy_format
        merged_results = reduce(lambda a, b: merge_results(a, b, merge_output_pnl, not original_timestamps), results)
        if legacy_format:
            write_output_legacy(output_file, merged_results)
        else:
            write_output(output_file, merged_results)
        print(f"\nSuccessfully saved backtest results to {format_path(output_file)}")

    if vis and output_file is not None:
        open_visualizer(output_file)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
