"""Pure parsing helpers for read-only price and surcharge data."""

import math
from datetime import datetime


def number(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Missing numeric value")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite numeric value")
    return result


def prices(payload):
    result = []
    for row in payload["prices"]:
        start = datetime.fromisoformat(row["startTime"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(row["endTime"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or end <= start:
            raise ValueError("Invalid price interval")
        if row.get("currency") != "DKK" or row.get("unit") != "kWh":
            raise ValueError("Unexpected price unit")
        result.append({"start": start.isoformat(), "end": end.isoformat(),
                       "price": number(row["totalPrice"]),
                       "tariffs": {k: number(v) for k, v in row.get("tariffs", {}).items()}})
    return sorted(result, key=lambda row: row["start"])


def surcharges(payload):
    # Deliberately omit daily arrays and all customer identifiers.
    result = [{"start": row["startDate"], "end": row["endDate"],
               "price": number(row["energySurchargePriceDkk"]),
               "average_price": number(row["averagePriceDkk"]),
               "threshold": number(row["cutOffPriceDkk"])} for row in payload]
    return sorted(result, key=lambda row: row["start"])
