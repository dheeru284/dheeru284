from datetime import datetime, timedelta

from optionpulse.macro import FACTORS, FactorSeries, MacroPoint, Regime, regime_at, snapshot
from optionpulse.session import IST


def series(values_by_time):
    return FactorSeries([MacroPoint(timestamp=t, value=v) for t, v in values_by_time])


Y = datetime(2026, 10, 27, 23, 0, tzinfo=IST)  # yesterday evening
T = datetime(2026, 10, 28, 11, 0, tzinfo=IST)


def test_change_is_measured_against_the_last_value_before_midnight():
    s = series([(Y - timedelta(hours=2), 70.0), (Y, 80.0), (T - timedelta(hours=1), 82.0), (T, 84.0)])
    assert s.value_at(T) == 84.0
    assert s.reference_at(T) == 80.0
    assert round(s.change_pct_at(T), 6) == 5.0
    assert s.value_at(T - timedelta(hours=1, minutes=30)) == 80.0  # as-of, no look-ahead
    assert s.session_values(T) == [82.0, 84.0]


def test_change_unknown_without_reference():
    s = series([(T, 84.0)])
    assert s.change_pct_at(T) is None
    assert series([]).value_at(T) is None


def _regime(brent=0.0, vix=0.0, usdinr=0.0):
    def make(pct):
        return series([(Y, 100.0), (T, 100.0 * (1 + pct / 100))])
    return regime_at({"BRENT": make(brent), "INDIAVIX": make(vix), "USDINR": make(usdinr)}, T)


def test_regimes():
    assert _regime().regime is Regime.NEUTRAL
    off = _regime(brent=2.0)
    assert off.regime is Regime.RISK_OFF and "Brent" in off.reasons[0]
    assert _regime(vix=6.0).regime is Regime.RISK_OFF
    assert _regime(usdinr=0.5).regime is Regime.RISK_OFF
    assert _regime(vix=-5.0).regime is Regime.RISK_ON
    assert _regime(brent=2.0, vix=-5.0).regime is Regime.NEUTRAL  # conflicting signals
    assert regime_at({}, T).regime is Regime.UNKNOWN


def test_snapshot_handles_missing_series():
    snap = snapshot(FACTORS[0], None, T, error="HTTP 429")
    assert snap.value is None and snap.error == "HTTP 429" and snap.sparkline == []
