import csv
from collections import defaultdict
from dataclasses import dataclass

from prosperity4bt.datamodel import Symbol, Trade
from prosperity4bt.file_reader import FileReader

LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}


@dataclass
class PriceRow:
    day: int
    timestamp: int
    product: Symbol
    bid_prices: list[int]
    bid_volumes: list[int]
    ask_prices: list[int]
    ask_volumes: list[int]
    mid_price: float
    profit_loss: float


@dataclass
class ConversionObservationRow:
    bid_price: float
    ask_price: float
    transport_fees: float
    export_tariff: float
    import_tariff: float
    sunlight: float
    humidity: float


@dataclass
class ObservationRow:
    timestamp: int
    plain_values: dict[Symbol, int]
    conversion_observations: dict[Symbol, ConversionObservationRow]


@dataclass
class BacktestData:
    round_num: int
    day_num: int

    prices: dict[int, dict[Symbol, PriceRow]]
    trades: dict[int, dict[Symbol, list[Trade]]]
    observations: dict[int, ObservationRow]
    products: list[Symbol]
    profit_loss: dict[Symbol, float]


def get_column_values(columns: list[str], indices: list[int]) -> list[int]:
    values = []

    for index in indices:
        value = columns[index]
        if value == "":
            break

        values.append(int(float(value)))

    return values


def create_backtest_data(
    round_num: int,
    day_num: int,
    prices: list[PriceRow],
    trades: list[Trade],
    observations: list[ObservationRow],
) -> BacktestData:
    prices_by_timestamp: dict[int, dict[Symbol, PriceRow]] = defaultdict(dict)
    for row in prices:
        prices_by_timestamp[row.timestamp][row.product] = row

    trades_by_timestamp: dict[int, dict[Symbol, list[Trade]]] = defaultdict(lambda: defaultdict(list))
    for trade in trades:
        trades_by_timestamp[trade.timestamp][trade.symbol].append(trade)

    products = sorted(set(row.product for row in prices))
    profit_loss = {product: 0.0 for product in products}
    observations_by_timestamp = {row.timestamp: row for row in observations}

    return BacktestData(
        round_num=round_num,
        day_num=day_num,
        prices=prices_by_timestamp,
        trades=trades_by_timestamp,
        observations=observations_by_timestamp,
        products=products,
        profit_loss=profit_loss,
    )


def has_day_data(file_reader: FileReader, round_num: int, day_num: int) -> bool:
    with file_reader.file([f"round{round_num}", f"prices_round_{round_num}_day_{day_num}.csv"]) as file:
        return file is not None


def normalize_field_name(name: str) -> str:
    return "".join(char.lower() for char in name if char.isalnum())


def get_required_str(row: dict[str, str], *aliases: str) -> str:
    normalized = {normalize_field_name(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(normalize_field_name(alias), "")
        if value != "":
            return value

    raise ValueError(f"Missing required observation column. Tried aliases: {', '.join(aliases)}")


def get_optional_str(row: dict[str, str], *aliases: str, default: str = "") -> str:
    normalized = {normalize_field_name(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(normalize_field_name(alias), "")
        if value != "":
            return value

    return default


def get_optional_float(row: dict[str, str], *aliases: str, default: float = 0.0) -> float:
    value = get_optional_str(row, *aliases)
    return float(value) if value != "" else default


def get_optional_int(row: dict[str, str], *aliases: str, default: int = 0) -> int:
    value = get_optional_str(row, *aliases)
    return int(float(value)) if value != "" else default


def parse_observation_rows(contents: str) -> list[ObservationRow]:
    lines = contents.splitlines()
    if len(lines) <= 1:
        return []

    delimiter = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    reader = csv.DictReader(lines, delimiter=delimiter)

    observations_by_timestamp: dict[int, ObservationRow] = {}
    for row in reader:
        timestamp = get_optional_int(row, "timestamp")
        product = get_optional_str(row, "product", "symbol", default="")

        if timestamp not in observations_by_timestamp:
            observations_by_timestamp[timestamp] = ObservationRow(
                timestamp=timestamp,
                plain_values={},
                conversion_observations={},
            )

        observation = observations_by_timestamp[timestamp]

        plain_value = get_optional_str(row, "observation", "value", "plainValue", default="")
        if plain_value != "" and product != "":
            observation.plain_values[product] = int(float(plain_value))

        if product == "":
            continue

        conversion_observation = ConversionObservationRow(
            bid_price=get_optional_float(row, "bidPrice", "bid_price"),
            ask_price=get_optional_float(row, "askPrice", "ask_price"),
            transport_fees=get_optional_float(row, "transportFees", "transport_fees"),
            export_tariff=get_optional_float(row, "exportTariff", "export_tariff"),
            import_tariff=get_optional_float(row, "importTariff", "import_tariff"),
            sunlight=get_optional_float(row, "sunlight", "sunlightIndex", "sunlight_index"),
            humidity=get_optional_float(row, "humidity"),
        )

        if any(
            (
                conversion_observation.bid_price,
                conversion_observation.ask_price,
                conversion_observation.transport_fees,
                conversion_observation.export_tariff,
                conversion_observation.import_tariff,
                conversion_observation.sunlight,
                conversion_observation.humidity,
            )
        ):
            observation.conversion_observations[product] = conversion_observation

    return list(observations_by_timestamp.values())


def read_day_data(file_reader: FileReader, round_num: int, day_num: int, no_names: bool) -> BacktestData:
    del no_names

    prices = []
    with file_reader.file([f"round{round_num}", f"prices_round_{round_num}_day_{day_num}.csv"]) as file:
        if file is None:
            raise ValueError(f"Prices data is not available for round {round_num} day {day_num}")

        for line in file.read_text(encoding="utf-8").splitlines()[1:]:
            columns = line.split(";")

            prices.append(
                PriceRow(
                    day=int(columns[0]),
                    timestamp=int(columns[1]),
                    product=columns[2],
                    bid_prices=get_column_values(columns, [3, 5, 7]),
                    bid_volumes=get_column_values(columns, [4, 6, 8]),
                    ask_prices=get_column_values(columns, [9, 11, 13]),
                    ask_volumes=get_column_values(columns, [10, 12, 14]),
                    mid_price=float(columns[15]),
                    profit_loss=float(columns[16]),
                )
            )

    trades = []
    with file_reader.file([f"round{round_num}", f"trades_round_{round_num}_day_{day_num}.csv"]) as file:
        if file is not None:
            for line in file.read_text(encoding="utf-8").splitlines()[1:]:
                columns = line.split(";")

                trades.append(
                    Trade(
                        symbol=columns[3],
                        price=int(float(columns[5])),
                        quantity=int(columns[6]),
                        buyer=columns[1],
                        seller=columns[2],
                        timestamp=int(columns[0]),
                    )
                )

    observations = []
    with file_reader.file([f"round{round_num}", f"observations_round_{round_num}_day_{day_num}.csv"]) as file:
        if file is not None:
            observations = parse_observation_rows(file.read_text(encoding="utf-8"))

    return create_backtest_data(round_num, day_num, prices, trades, observations)
