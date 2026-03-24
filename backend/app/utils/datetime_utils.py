from datetime import UTC, datetime


def unix_to_minute_datetime(value: object) -> str | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value.astimezone(UTC)
        return dt.strftime("%Y-%m-%d %H:%M")

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return _from_unix_number(float(raw))
        return raw

    if isinstance(value, (int, float)):
        return _from_unix_number(float(value))

    return str(value)


def _from_unix_number(unix_value: float) -> str:
    # Databricks timestamps can be in milliseconds.
    timestamp_seconds = unix_value / 1000 if unix_value > 1_000_000_000_000 else unix_value
    dt = datetime.fromtimestamp(timestamp_seconds, tz=UTC)
    return dt.strftime("%Y-%m-%d %H:%M")
