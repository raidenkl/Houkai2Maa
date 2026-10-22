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
STOP_DEATH_LIMIT = "death_limit"
STOP_UNKNOWN_LIMIT = "unknown_limit"

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
    #: 死亡（战斗失败后走「救救我→返回→退出关卡」）次数上限
    max_deaths: int = 2
    #: 连续无法识别场景的次数上限：超过就认为界面卡死，收尾而不是乱点
    max_unknown: int = 3
    #: 体力兑换（+2）每轮任务允许用几次。游戏里本身只能换一次，这是显式替代
    #: `max_hit: 1` 的地方 —— 后者是「整次任务累计」，第二轮会整段跳过。
    exchange_limit: int = 1

    def __post_init__(self) -> None:
        if self.max_times < 0:
            raise ValueError("max_times 不能为负")
        if self.max_failures < 0:
            raise ValueError("max_failures 不能为负")
        if self.max_deaths < 0:
            raise ValueError("max_deaths 不能为负")
        if self.max_unknown < 0:
            raise ValueError("max_unknown 不能为负")
        if self.exchange_limit < 0:
            raise ValueError("exchange_limit 不能为负")


@dataclass
class FarmProgress:
    """执行进度。"""

    battles: int = 0
    failures: int = 0
    deaths: int = 0
    #: 遇到的「未知场景」次数，用于判断界面卡死
    unknown: int = 0
    #: 本轮（一键日常的「第几轮」）序号，从 1 开始
    rounds: int = 0
    #: 体力兑换已用次数（跨轮累计，与游戏本身的一次性限制对齐）
    exchange_used: int = 0
    stamina_insufficient: bool = False
    #: 见到水晶购买窗即视为「本轮确实没体力了」，用来区分「误触」与「真没体力」
    crystal_seen: bool = False
    #: 是否正处在一场战斗的流程里（备战/助战/开战/等待）
    in_round: bool = False
    #: 上一次路由是否进入了「会开打」的节点；只有它为真时结算才计一场，
    #: 防止「再来一次」后残留的结算帧被重复计数。
    expect_battle: bool = False
    stop_reason: str = ""
    last_scene: str = ""

    def reset(self) -> None:
        self.battles = 0
        self.failures = 0
        self.deaths = 0
        self.unknown = 0
        self.rounds = 0
        self.exchange_used = 0
        self.stamina_insufficient = False
        self.crystal_seen = False
        self.in_round = False
        self.expect_battle = False
        self.stop_reason = ""
        self.last_scene = ""

    def note_stamina_insufficient(self) -> None:
        """由 pipeline 的「体力不足」分支显式打标（`FarmNote` 动作）。"""

        self.stamina_insufficient = True

    def consume_stamina_flag(self) -> bool:
        """读取并清除标记，保证一次体力不足只影响一次判定。"""

        flag = self.stamina_insufficient
        self.stamina_insufficient = False
        return flag

    def record_battle(self) -> None:
        self.battles += 1

    def record_failure(self) -> None:
        self.failures += 1

    def record_death(self) -> None:
        self.deaths += 1

    def record_unknown(self) -> None:
        self.unknown += 1

    def record_exchange(self) -> None:
        self.exchange_used += 1

    def begin_round(self) -> bool:
        """进入一轮新的刷本循环。

        返回 True 表示「这是一个新轮次」。轮次之间要塞进「勤劳的魔女」领 100 体力，
        所以必须清掉上一轮留下的体力标志；而 `battles` / `exchange_used` 是整次任务
        累计，不能清（否则第二轮的兑换次数与场次上限都会失效）。
        """

        if self.in_round:
            return False
        self.rounds += 1
        self.in_round = True
        self.unknown = 0
        self.stamina_insufficient = False
        self.crystal_seen = False
        self.expect_battle = False
        return True


def decide_stop(
    plan: FarmPlan,
    progress: FarmProgress,
    stamina_insufficient: bool = False,
) -> tuple[bool, str]:
    """返回 (是否停止, 原因)。

    优先级：失败上限 > 死亡上限 > 未知场景上限 > 体力不足 > 次数达标。
    死亡/未知排在前面的理由：这两种情况继续跑只会卡在同一个界面空转。
    """

    if plan.max_failures and progress.failures >= plan.max_failures:
        return True, STOP_FAILURE_LIMIT
    if plan.max_deaths and progress.deaths >= plan.max_deaths:
        return True, STOP_DEATH_LIMIT
    if plan.max_unknown and progress.unknown >= plan.max_unknown:
        return True, STOP_UNKNOWN_LIMIT
    if stamina_insufficient and plan.until_no_stamina:
        return True, STOP_STAMINA
    if plan.max_times and progress.battles >= plan.max_times:
        return True, STOP_TARGET
    return False, ""
