# SPDX-License-Identifier: MIT
"""ADAAD Phase 9 — Revenue Growth Engine.

Modules:
  customer_health   — health scoring, churn prediction
  trial_conversion  — free-to-paid conversion nudges
  revenue_analytics — MRR/ARR/cohort analytics
"""

from runtime.growth.customer_health import (
    CustomerHealthScorer,
    HealthReport,
    HealthScore,
    RiskBand,
    UsageSnapshot,
    compute_health,
)
from runtime.growth.trial_conversion import (
    ConversionEvent,
    ConversionTrigger,
    TrialConversionEngine,
    UpgradeNudge,
)
from runtime.growth.revenue_analytics import (
    MRRWaterfall,
    OrgBillingRecord,
    RevenueAnalyticsService,
    RevenueSnapshot,
    compute_snapshot,
    compute_payback_period,
)

__all__ = [
    # health
    "CustomerHealthScorer",
    "HealthReport",
    "HealthScore",
    "RiskBand",
    "UsageSnapshot",
    "compute_health",
    # conversion
    "ConversionEvent",
    "ConversionTrigger",
    "TrialConversionEngine",
    "UpgradeNudge",
    # analytics
    "MRRWaterfall",
    "OrgBillingRecord",
    "RevenueAnalyticsService",
    "RevenueSnapshot",
    "compute_snapshot",
    "compute_payback_period",
]
