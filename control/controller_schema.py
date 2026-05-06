"""Schema và giá trị mặc định cho action của controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy

from ml.feature_schema import ACTION_OUTPUT_COLUMNS


@dataclass(slots=True)
class ControllerConstraints:
    min_ratio: float = 0.05
    max_ratio: float = 0.90
    max_step_change: float = 0.10
    scheduling_weight_floor: float = 0.50
    scheduling_weight_ceiling: float = 3.00
    admission_guard_floor: float = 0.80
    admission_guard_ceiling: float = 1.50
    min_ratio_by_slice: dict[str, float] = field(default_factory=dict)
    max_ratio_by_slice: dict[str, float] = field(default_factory=dict)


DEFAULT_PRIORITY_WEIGHTS = {
    "URLLC": 1.30,
    "eMBB": 1.00,
    "mMTC": 0.80,
}


@dataclass(slots=True)
class ControllerPreset:
    name: str
    description: str
    alpha_risk: float
    beta_load: float
    gamma_latency: float
    delta_priority: float
    scheduling_risk_gain: float = 1.0
    scheduling_latency_gain: float = 1.0
    scheduling_load_gain: float = 0.0
    admission_risk_gain: float = 0.5
    admission_block_gain: float = 0.25
    risk_probability_ceiling: float = 1.0
    admission_hysteresis_high_threshold: float = 1.0
    admission_hysteresis_low_threshold: float = 0.0
    admission_hysteresis_windows: int = 1
    admission_hysteresis_warmup_factor: float = 1.0
    urllc_first_service_gain: float = 0.0
    urllc_scheduling_bonus: float = 0.0
    urllc_admission_guard_bonus: float = 0.0
    non_urllc_scheduling_backoff: float = 0.0
    non_urllc_admission_guard_bonus: float = 0.0
    slice_ratio_biases: dict[str, float] = field(default_factory=dict)
    action_optimizer_enabled: bool = False
    optimizer_current_anchor: float = 0.55
    optimizer_demand_gain: float = 0.30
    optimizer_risk_gain: float = 0.15
    optimizer_move_penalty: float = 0.40
    optimizer_prior_gain: float = 0.00
    optimizer_prior_penalty: float = 0.00
    optimizer_starvation_floor: float = 0.08
    optimizer_ratio_prior_by_slice: dict[str, float] = field(default_factory=dict)
    optimization_qp_enabled: bool = False
    qp_mu: float = 0.20
    qp_load_gain: float = 0.40
    qp_latency_gain: float = 0.30
    qp_min_objective_weight: float = 0.05
    dynamic_borrow_enabled: bool = False
    borrow_intensity: float = 0.50
    borrow_load_threshold: float = 0.45
    borrow_risk_threshold: float = 0.65
    adaptive_step_enabled: bool = False
    adaptive_step_kappa: float = 1.00
    adaptive_step_ceiling: float | None = None
    priority_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PRIORITY_WEIGHTS))
    constraints: ControllerConstraints = field(default_factory=ControllerConstraints)


DEFAULT_CONTROLLER_PRESETS = {
    "balanced": ControllerPreset(
        name="balanced",
        description="Controller cân bằng hiện tại, kết hợp risk dự đoán, load, latency pressure và priority của slice.",
        alpha_risk=0.45,
        beta_load=0.25,
        gamma_latency=0.20,
        delta_priority=0.10,
        scheduling_risk_gain=1.00,
        scheduling_latency_gain=1.00,
        scheduling_load_gain=0.20,
        admission_risk_gain=0.50,
        admission_block_gain=0.25,
        urllc_first_service_gain=0.00,
        urllc_scheduling_bonus=0.00,
        urllc_admission_guard_bonus=0.00,
        non_urllc_scheduling_backoff=0.00,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={},
        priority_weights=dict(DEFAULT_PRIORITY_WEIGHTS),
        constraints=ControllerConstraints(),
    ),
    "latency_priority": ControllerPreset(
        name="latency_priority",
        description="Tăng bảo vệ cho các slice nhạy với latency, đặc biệt là URLLC, với action step lớn hơn một chút.",
        alpha_risk=0.35,
        beta_load=0.15,
        gamma_latency=0.35,
        delta_priority=0.15,
        scheduling_risk_gain=1.15,
        scheduling_latency_gain=1.35,
        scheduling_load_gain=0.10,
        admission_risk_gain=0.65,
        admission_block_gain=0.35,
        urllc_first_service_gain=0.40,
        urllc_scheduling_bonus=0.35,
        urllc_admission_guard_bonus=0.10,
        non_urllc_scheduling_backoff=0.05,
        non_urllc_admission_guard_bonus=0.05,
        slice_ratio_biases={"URLLC": 0.02},
        priority_weights={"URLLC": 1.60, "eMBB": 0.95, "mMTC": 0.70},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.90,
            max_step_change=0.15,
            scheduling_weight_floor=0.50,
            scheduling_weight_ceiling=3.50,
            admission_guard_floor=0.85,
            admission_guard_ceiling=1.70,
        ),
    ),
    "aggressive": ControllerPreset(
        name="aggressive",
        description="Controller phản ứng mạnh hơn, đẩy ratio và policy quyết liệt hơn khi risk vi phạm SLA tăng đột biến.",
        alpha_risk=0.55,
        beta_load=0.20,
        gamma_latency=0.15,
        delta_priority=0.10,
        scheduling_risk_gain=1.45,
        scheduling_latency_gain=1.10,
        scheduling_load_gain=0.30,
        admission_risk_gain=0.85,
        admission_block_gain=0.40,
        urllc_first_service_gain=0.25,
        urllc_scheduling_bonus=0.20,
        urllc_admission_guard_bonus=0.10,
        non_urllc_scheduling_backoff=0.05,
        non_urllc_admission_guard_bonus=0.05,
        slice_ratio_biases={"URLLC": 0.02},
        priority_weights={"URLLC": 1.40, "eMBB": 1.00, "mMTC": 0.75},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.90,
            max_step_change=0.20,
            scheduling_weight_floor=0.50,
            scheduling_weight_ceiling=4.00,
            admission_guard_floor=0.80,
            admission_guard_ceiling=1.80,
        ),
    ),
    "urllc_first_service_v2": ControllerPreset(
        name="urllc_first_service_v2",
        description="Controller v2 bảo vệ rõ ràng first-service latency của URLLC bằng các chỉ báo burst và queue, đồng thời giảm ưu tiên các slice không phải URLLC khi URLLC chịu áp lực cao.",
        alpha_risk=0.28,
        beta_load=0.10,
        gamma_latency=0.24,
        delta_priority=0.38,
        scheduling_risk_gain=1.15,
        scheduling_latency_gain=1.55,
        scheduling_load_gain=0.05,
        admission_risk_gain=0.75,
        admission_block_gain=0.45,
        urllc_first_service_gain=1.75,
        urllc_scheduling_bonus=1.40,
        urllc_admission_guard_bonus=0.35,
        non_urllc_scheduling_backoff=0.22,
        non_urllc_admission_guard_bonus=0.18,
        slice_ratio_biases={"URLLC": 0.08, "eMBB": -0.04, "mMTC": -0.02},
        priority_weights={"URLLC": 2.10, "eMBB": 0.85, "mMTC": 0.65},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.90,
            max_step_change=0.18,
            scheduling_weight_floor=0.45,
            scheduling_weight_ceiling=4.50,
            admission_guard_floor=0.85,
            admission_guard_ceiling=1.95,
        ),
    ),
    "balanced_ml_v2": ControllerPreset(
        name="balanced_ml_v2",
        description="ML controller cân bằng, vẫn giữ bảo vệ cho URLLC nhưng thêm ratio floor tối thiểu theo từng slice để giảm starvation của eMBB và mMTC.",
        alpha_risk=0.34,
        beta_load=0.24,
        gamma_latency=0.22,
        delta_priority=0.20,
        scheduling_risk_gain=1.05,
        scheduling_latency_gain=1.15,
        scheduling_load_gain=0.18,
        admission_risk_gain=0.55,
        admission_block_gain=0.30,
        urllc_first_service_gain=0.65,
        urllc_scheduling_bonus=0.55,
        urllc_admission_guard_bonus=0.16,
        non_urllc_scheduling_backoff=0.06,
        non_urllc_admission_guard_bonus=0.05,
        slice_ratio_biases={"URLLC": 0.02, "eMBB": 0.01, "mMTC": 0.00},
        priority_weights={"URLLC": 1.45, "eMBB": 1.00, "mMTC": 0.85},
        constraints=ControllerConstraints(
            min_ratio=0.08,
            max_ratio=0.72,
            max_step_change=0.10,
            scheduling_weight_floor=0.55,
            scheduling_weight_ceiling=3.20,
            admission_guard_floor=0.85,
            admission_guard_ceiling=1.65,
            min_ratio_by_slice={"URLLC": 0.28, "eMBB": 0.18, "mMTC": 0.12},
        ),
    ),
    "balanced_ml_v3_gentle": ControllerPreset(
        name="balanced_ml_v3_gentle",
        description=(
            "ML controller nhẹ tay: giảm admission gating để tránh vòng lặp block_ratio khi risk score cao. "
            "Phù hợp với model GBDT đã loại bỏ feature SLA-derived (no-leak) — risk score đáng tin cậy hơn nên controller "
            "không cần phản ứng quá hung hãn ở cửa admission. Ưu tiên vẫn dành cho URLLC nhưng giảm starvation cho eMBB/mMTC."
        ),
        alpha_risk=0.30,
        beta_load=0.28,
        gamma_latency=0.22,
        delta_priority=0.20,
        scheduling_risk_gain=1.00,
        scheduling_latency_gain=1.10,
        scheduling_load_gain=0.20,
        admission_risk_gain=0.30,
        admission_block_gain=0.05,
        risk_probability_ceiling=0.85,
        admission_hysteresis_high_threshold=0.75,
        admission_hysteresis_low_threshold=0.45,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.35,
        urllc_first_service_gain=0.55,
        urllc_scheduling_bonus=0.45,
        urllc_admission_guard_bonus=0.03,
        non_urllc_scheduling_backoff=0.04,
        non_urllc_admission_guard_bonus=0.02,
        slice_ratio_biases={"URLLC": 0.02, "eMBB": 0.01, "mMTC": 0.00},
        priority_weights={"URLLC": 1.40, "eMBB": 1.00, "mMTC": 0.85},
        constraints=ControllerConstraints(
            min_ratio=0.10,
            max_ratio=0.70,
            max_step_change=0.08,
            scheduling_weight_floor=0.60,
            scheduling_weight_ceiling=2.80,
            admission_guard_floor=0.90,
            admission_guard_ceiling=1.15,
            min_ratio_by_slice={"URLLC": 0.20, "eMBB": 0.15, "mMTC": 0.10},
        ),
    ),
    "guarded_ml_optimizer_v1": ControllerPreset(
        name="guarded_ml_optimizer_v1",
        description=(
            "Guarded ML action optimizer: use GBDT risk as a soft signal, keep actions close to the current "
            "baseline allocation, prefer scheduling/ratio adjustments, and avoid aggressive admission blocking."
        ),
        alpha_risk=0.18,
        beta_load=0.42,
        gamma_latency=0.22,
        delta_priority=0.18,
        scheduling_risk_gain=0.45,
        scheduling_latency_gain=0.55,
        scheduling_load_gain=0.35,
        admission_risk_gain=0.04,
        admission_block_gain=0.00,
        risk_probability_ceiling=0.75,
        admission_hysteresis_high_threshold=0.82,
        admission_hysteresis_low_threshold=0.50,
        admission_hysteresis_windows=3,
        admission_hysteresis_warmup_factor=0.20,
        urllc_first_service_gain=0.28,
        urllc_scheduling_bonus=0.30,
        urllc_admission_guard_bonus=0.00,
        non_urllc_scheduling_backoff=0.01,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={"URLLC": 0.005, "eMBB": 0.015, "mMTC": 0.005},
        action_optimizer_enabled=True,
        optimizer_current_anchor=0.35,
        optimizer_demand_gain=0.15,
        optimizer_risk_gain=0.05,
        optimizer_move_penalty=0.40,
        optimizer_prior_gain=0.45,
        optimizer_prior_penalty=0.65,
        optimizer_starvation_floor=0.06,
        optimizer_ratio_prior_by_slice={"URLLC": 0.16, "eMBB": 0.64, "mMTC": 0.20},
        priority_weights={"URLLC": 1.22, "eMBB": 1.00, "mMTC": 0.88},
        constraints=ControllerConstraints(
            min_ratio=0.03,
            max_ratio=0.78,
            max_step_change=0.030,
            scheduling_weight_floor=0.75,
            scheduling_weight_ceiling=1.85,
            admission_guard_floor=0.96,
            admission_guard_ceiling=1.06,
            min_ratio_by_slice={"URLLC": 0.12, "eMBB": 0.56, "mMTC": 0.12},
        ),
    ),
    "balanced_ml_v4_demand_aware": ControllerPreset(
        name="balanced_ml_v4_demand_aware",
        description=(
            "Controller v4: bỏ floor cứng theo slice để target_ratio bám theo cầu thực tế. "
            "Thiết kế đi cùng broker forecasting_demand_aware (no fairness floor) và bản fix "
            "_demand_signal trong traffic_forecaster (BS-relative) để eMBB không bị siết khi cầu cao. "
            "Vẫn giữ ưu tiên URLLC qua priority_weights và urllc_first_service_gain, nhưng admission "
            "không gating quá mạnh khi prob risk cao (admission_risk_gain thấp + admission_guard_ceiling 1.15)."
        ),
        alpha_risk=0.28,
        beta_load=0.30,
        gamma_latency=0.22,
        delta_priority=0.20,
        scheduling_risk_gain=0.95,
        scheduling_latency_gain=1.05,
        scheduling_load_gain=0.25,
        admission_risk_gain=0.18,
        admission_block_gain=0.04,
        risk_probability_ceiling=0.85,
        admission_hysteresis_high_threshold=0.78,
        admission_hysteresis_low_threshold=0.45,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.30,
        urllc_first_service_gain=0.50,
        urllc_scheduling_bonus=0.40,
        urllc_admission_guard_bonus=0.02,
        non_urllc_scheduling_backoff=0.03,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={"URLLC": 0.02, "eMBB": 0.01, "mMTC": 0.00},
        priority_weights={"URLLC": 1.35, "eMBB": 1.00, "mMTC": 0.85},
        constraints=ControllerConstraints(
            min_ratio=0.08,
            max_ratio=0.78,
            max_step_change=0.10,
            scheduling_weight_floor=0.60,
            scheduling_weight_ceiling=2.80,
            admission_guard_floor=0.92,
            admission_guard_ceiling=1.15,
            min_ratio_by_slice={},
        ),
    ),
    "balanced_ml_v5_qp_borrow": ControllerPreset(
        name="balanced_ml_v5_qp_borrow",
        description=(
            "Optimization-based controller: replace heuristic urgency allocation with a per-BS quadratic program "
            "and a dynamic capacity-borrowing pass. The QP pulls high-risk/high-load slices toward their upper "
            "bounded ratios while penalizing large moves from the previous ratio."
        ),
        alpha_risk=0.24,
        beta_load=0.30,
        gamma_latency=0.22,
        delta_priority=0.24,
        scheduling_risk_gain=0.80,
        scheduling_latency_gain=0.90,
        scheduling_load_gain=0.20,
        admission_risk_gain=0.12,
        admission_block_gain=0.03,
        risk_probability_ceiling=0.82,
        admission_hysteresis_high_threshold=0.80,
        admission_hysteresis_low_threshold=0.48,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.25,
        urllc_first_service_gain=0.42,
        urllc_scheduling_bonus=0.34,
        urllc_admission_guard_bonus=0.01,
        non_urllc_scheduling_backoff=0.02,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={},
        optimization_qp_enabled=True,
        qp_mu=0.18,
        qp_load_gain=0.55,
        qp_latency_gain=0.30,
        qp_min_objective_weight=0.04,
        dynamic_borrow_enabled=True,
        borrow_intensity=0.55,
        borrow_load_threshold=0.42,
        borrow_risk_threshold=0.62,
        priority_weights={"URLLC": 1.35, "eMBB": 1.00, "mMTC": 0.88},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.80,
            max_step_change=0.08,
            scheduling_weight_floor=0.65,
            scheduling_weight_ceiling=2.60,
            admission_guard_floor=0.94,
            admission_guard_ceiling=1.12,
            min_ratio_by_slice={},
        ),
    ),
    "balanced_ml_v6_adaptive_qp": ControllerPreset(
        name="balanced_ml_v6_adaptive_qp",
        description=(
            "V6 adaptive QP controller: keep the v5 QP + dynamic borrow design, but use per-slice "
            "adaptive max_step_change from recent risk shocks so the controller converges faster during bursts "
            "and stays smooth when the state is stable."
        ),
        alpha_risk=0.24,
        beta_load=0.30,
        gamma_latency=0.22,
        delta_priority=0.24,
        scheduling_risk_gain=0.78,
        scheduling_latency_gain=0.88,
        scheduling_load_gain=0.22,
        admission_risk_gain=0.10,
        admission_block_gain=0.02,
        risk_probability_ceiling=0.82,
        admission_hysteresis_high_threshold=0.80,
        admission_hysteresis_low_threshold=0.48,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.25,
        urllc_first_service_gain=0.42,
        urllc_scheduling_bonus=0.34,
        urllc_admission_guard_bonus=0.01,
        non_urllc_scheduling_backoff=0.02,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={},
        optimization_qp_enabled=True,
        qp_mu=0.18,
        qp_load_gain=0.55,
        qp_latency_gain=0.30,
        qp_min_objective_weight=0.04,
        dynamic_borrow_enabled=True,
        borrow_intensity=0.55,
        borrow_load_threshold=0.42,
        borrow_risk_threshold=0.62,
        adaptive_step_enabled=True,
        adaptive_step_kappa=1.50,
        adaptive_step_ceiling=0.16,
        priority_weights={"URLLC": 1.35, "eMBB": 1.00, "mMTC": 0.88},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.82,
            max_step_change=0.06,
            scheduling_weight_floor=0.65,
            scheduling_weight_ceiling=2.55,
            admission_guard_floor=0.94,
            admission_guard_ceiling=1.10,
            min_ratio_by_slice={},
        ),
    ),
    "balanced_ml_v7_tail_guard": ControllerPreset(
        name="balanced_ml_v7_tail_guard",
        description=(
            "V7 tail-guard QP controller: keeps the v6 adaptive QP path but caps eMBB growth, "
            "reduces dynamic borrowing, and preserves URLLC/mMTC floors to avoid heavy-load p95 latency regression."
        ),
        alpha_risk=0.22,
        beta_load=0.24,
        gamma_latency=0.28,
        delta_priority=0.26,
        scheduling_risk_gain=0.70,
        scheduling_latency_gain=1.00,
        scheduling_load_gain=0.16,
        admission_risk_gain=0.08,
        admission_block_gain=0.02,
        risk_probability_ceiling=0.78,
        admission_hysteresis_high_threshold=0.78,
        admission_hysteresis_low_threshold=0.46,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.25,
        urllc_first_service_gain=0.46,
        urllc_scheduling_bonus=0.42,
        urllc_admission_guard_bonus=0.01,
        non_urllc_scheduling_backoff=0.04,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={},
        optimization_qp_enabled=True,
        qp_mu=0.24,
        qp_load_gain=0.42,
        qp_latency_gain=0.45,
        qp_min_objective_weight=0.05,
        dynamic_borrow_enabled=True,
        borrow_intensity=0.25,
        borrow_load_threshold=0.55,
        borrow_risk_threshold=0.70,
        adaptive_step_enabled=True,
        adaptive_step_kappa=0.90,
        adaptive_step_ceiling=0.10,
        priority_weights={"URLLC": 1.50, "eMBB": 1.00, "mMTC": 0.95},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.76,
            max_step_change=0.045,
            scheduling_weight_floor=0.70,
            scheduling_weight_ceiling=2.45,
            admission_guard_floor=0.94,
            admission_guard_ceiling=1.08,
            min_ratio_by_slice={"URLLC": 0.12, "eMBB": 0.52, "mMTC": 0.10},
            max_ratio_by_slice={"URLLC": 0.30, "eMBB": 0.74, "mMTC": 0.24},
        ),
    ),
    "balanced_ml_v8_latency_safe": ControllerPreset(
        name="balanced_ml_v8_latency_safe",
        description=(
            "V8 latency-safe QP controller: conservative heavy-load preset that limits eMBB near the baseline split, "
            "keeps stronger URLLC/mMTC floors, and minimizes borrow to protect global p95 latency."
        ),
        alpha_risk=0.24,
        beta_load=0.18,
        gamma_latency=0.34,
        delta_priority=0.24,
        scheduling_risk_gain=0.68,
        scheduling_latency_gain=1.10,
        scheduling_load_gain=0.10,
        admission_risk_gain=0.06,
        admission_block_gain=0.02,
        risk_probability_ceiling=0.75,
        admission_hysteresis_high_threshold=0.78,
        admission_hysteresis_low_threshold=0.46,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.20,
        urllc_first_service_gain=0.55,
        urllc_scheduling_bonus=0.50,
        urllc_admission_guard_bonus=0.01,
        non_urllc_scheduling_backoff=0.08,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={},
        optimization_qp_enabled=True,
        qp_mu=0.32,
        qp_load_gain=0.28,
        qp_latency_gain=0.58,
        qp_min_objective_weight=0.06,
        dynamic_borrow_enabled=True,
        borrow_intensity=0.10,
        borrow_load_threshold=0.68,
        borrow_risk_threshold=0.78,
        adaptive_step_enabled=True,
        adaptive_step_kappa=0.60,
        adaptive_step_ceiling=0.075,
        priority_weights={"URLLC": 1.65, "eMBB": 1.00, "mMTC": 1.05},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.70,
            max_step_change=0.035,
            scheduling_weight_floor=0.75,
            scheduling_weight_ceiling=2.35,
            admission_guard_floor=0.94,
            admission_guard_ceiling=1.06,
            min_ratio_by_slice={"URLLC": 0.16, "eMBB": 0.54, "mMTC": 0.14},
            max_ratio_by_slice={"URLLC": 0.30, "eMBB": 0.68, "mMTC": 0.26},
        ),
    ),
    "balanced_ml_v9_heavy_urllc_guard": ControllerPreset(
        name="balanced_ml_v9_heavy_urllc_guard",
        description=(
            "V9 heavy-load URLLC guard: keeps the v8 latency-safe QP path but raises the URLLC floor, "
            "caps eMBB harder, and makes latency pressure dominate load pressure to reduce heavy-scenario p95 regression."
        ),
        alpha_risk=0.24,
        beta_load=0.14,
        gamma_latency=0.40,
        delta_priority=0.22,
        scheduling_risk_gain=0.68,
        scheduling_latency_gain=1.22,
        scheduling_load_gain=0.08,
        admission_risk_gain=0.05,
        admission_block_gain=0.02,
        risk_probability_ceiling=0.75,
        admission_hysteresis_high_threshold=0.78,
        admission_hysteresis_low_threshold=0.46,
        admission_hysteresis_windows=2,
        admission_hysteresis_warmup_factor=0.20,
        urllc_first_service_gain=0.70,
        urllc_scheduling_bonus=0.62,
        urllc_admission_guard_bonus=0.01,
        non_urllc_scheduling_backoff=0.10,
        non_urllc_admission_guard_bonus=0.00,
        slice_ratio_biases={},
        optimization_qp_enabled=True,
        qp_mu=0.38,
        qp_load_gain=0.18,
        qp_latency_gain=0.72,
        qp_min_objective_weight=0.08,
        dynamic_borrow_enabled=True,
        borrow_intensity=0.04,
        borrow_load_threshold=0.78,
        borrow_risk_threshold=0.84,
        adaptive_step_enabled=True,
        adaptive_step_kappa=0.45,
        adaptive_step_ceiling=0.060,
        priority_weights={"URLLC": 1.80, "eMBB": 0.95, "mMTC": 1.05},
        constraints=ControllerConstraints(
            min_ratio=0.05,
            max_ratio=0.68,
            max_step_change=0.030,
            scheduling_weight_floor=0.78,
            scheduling_weight_ceiling=2.30,
            admission_guard_floor=0.95,
            admission_guard_ceiling=1.05,
            min_ratio_by_slice={"URLLC": 0.18, "eMBB": 0.50, "mMTC": 0.14},
            max_ratio_by_slice={"URLLC": 0.34, "eMBB": 0.64, "mMTC": 0.28},
        ),
    ),
}


def get_controller_preset(name: str) -> ControllerPreset:
    if name not in DEFAULT_CONTROLLER_PRESETS:
        valid_names = ", ".join(sorted(DEFAULT_CONTROLLER_PRESETS))
        raise ValueError(f"Unknown controller preset '{name}'. Valid presets: {valid_names}")
    return deepcopy(DEFAULT_CONTROLLER_PRESETS[name])


DEFAULT_ACTION_COLUMNS = ACTION_OUTPUT_COLUMNS
