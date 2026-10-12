"""Contract-weather historical analysis outputs. Historical risk is never a prediction."""

from enum import StrEnum

from pydantic import Field

from .common import StrictModel


class CoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class YearCoverage(StrictModel):
    year: int
    variable: str
    requested_interval: str
    coverage_pct: float = Field(ge=0, le=100)
    status: CoverageStatus
    product_id: str | None = None
    dataset_id: str | None = None
    covered_intervals: list[str] = Field(default_factory=list)
    missing_intervals: list[str] = Field(default_factory=list)


class HistoricalRiskResult(StrictModel):
    mode: str = "HISTORICAL_SEASONAL_WEATHER_RISK"
    requested_years: list[int]
    analysed_years: list[int]
    all_requested_complete: bool
    coverage: list[YearCoverage]
    caveats: list[str] = Field(default_factory=list)
    risk_label: str | None = None
