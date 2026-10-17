"""刷本循环的纯状态逻辑。

与 MAA API 完全解耦，便于单元测试与回放复现。

约定：
* `FarmPlan` 是用户意图（刷几次 / 是否刷到没体力）；
* `FarmProgress` 是本次任务的执行记录；
* `decide_stop` 统一给出「是否停止 + 原因」，供自定义动作决定 `override_next`。
"""

from __future__ import annotations

from dataclasses import dataclass

STOP_STAMINA = "stamina"
STOP_TARGET = "target_reached"
STOP_FAILURE_LIMIT = "failure_limit"

STATE_CLAIMED = "claimed"
STATE_AVAILABLE = "available"


def classify_panel(claimed_hit: bool, available_hit: bool) -> str | None:
    """把「已领取」「可领取」两个识别结果映射为面板状态。

    两者同时命中（或都不命中）视为不可判定，返回 None 交给 pipeline 处理，
    避免误点。
    """

    if claimed_hit == available_hit:
        return None
    return STATE_CLAIMED if claimed_hit else STATE_AVAILABLE


@dataclass(frozen=True)
class FarmPlan:
    """刷本计划。max_times 为 0 表示不限次数。"""

    max_times: int = 0
    until_no_stamina: bool = False
    max_failures: int = 2

    def __post_init__(self) -> None:
        if self.max_times < 0:
            raise ValueError("max_times 不能为负")
        if self.max_failures < 0:
            raise ValueError("max_failures 不能为负")


@dataclass
class FarmProgress:
    """执行进度。"""

    battles: int = 0
    failures: int = 0

    def reset(self) -> None:
        self.battles = 0
        self.failures = 0

    def record_battle(self) -> None:
        self.battles += 1

    def record_failure(self) -> None:
        self.failures += 1


def decide_stop(
    plan: FarmPlan,
    progress: FarmProgress,
    stamina_insufficient: bool = False,
) -> tuple[bool, str]:
    """返回 (是否停止, 原因)。

    优先级：失败上限 > 体力不足 > 次数达标。
    """

    if plan.max_failures and progress.failures >= plan.max_failures:
        return True, STOP_FAILURE_LIMIT
    if stamina_insufficient and plan.until_no_stamina:
        return True, STOP_STAMINA
    if plan.max_times and progress.battles >= plan.max_times:
        return True, STOP_TARGET
    return False, ""
