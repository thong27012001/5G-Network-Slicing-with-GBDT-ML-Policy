"""Broker orchestrator for forecast -> admission planning -> feedback."""

from __future__ import annotations

import pandas as pd

from broker.admission_planner import ForecastingAdmissionPlanner
from broker.broker_schema import BrokerDecision, get_broker_config
from broker.sla_feedback import SlaFeedbackController
from broker.traffic_forecaster import TrafficForecaster


class SliceBroker:
    """Coordinate broker-level forecasting, planning, and feedback."""

    def __init__(self, controller, preset_name: str = "forecasting_balanced"):
        self.config = get_broker_config(preset_name)
        self.controller = controller
        self.forecaster = TrafficForecaster(self.config)
        self.feedback_controller = SlaFeedbackController(self.config)
        self.planner = ForecastingAdmissionPlanner(self.config, controller)

    def decide(
        self,
        state_df: pd.DataFrame, 
        history_df: pd.DataFrame,
        prediction_df: pd.DataFrame,
        effective_time: int | float,
    ) -> BrokerDecision:
        feedback = self.feedback_controller.update(state_df, effective_time=effective_time)
        forecasts = self.forecaster.forecast(
            history_df=history_df,
            state_df=state_df,
            safety_margins=self.feedback_controller.get_safety_margins(),
            effective_time=effective_time,
        )
        actions = self.planner.plan(
            state_df=state_df,
            prediction_df=prediction_df,
            forecast_df=forecasts,
            effective_time=effective_time,
        )
        return BrokerDecision(actions=actions, forecasts=forecasts, feedback=feedback)

