from app.services.bybit import _parse_internal_deposit_record


def test_parse_internal_deposit_record_normalizes_created_time_seconds_to_milliseconds() -> None:
    record = _parse_internal_deposit_record(
        {
            "txID": "tx-1",
            "amount": "100.00",
            "coin": "USDT",
            "status": "2",
            "fromMemberId": "777777",
            "createdTime": "1775055139",
        }
    )

    assert record.created_time_ms == 1775055139000
