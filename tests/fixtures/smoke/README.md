# smoke fixture

给 `tools/tests/test_dryrun.py` 用的最小资源包：两张 720p 截图 + 两个色块模板 +
一条三节点流水线（`SmokeEntry → SmokeStepA → SmokeStepB`）。

用途：在 CI 里验证「用截图离线跑流程」这条链路（StaticImageController +
dryrun）没有被改坏。图片是纯色块，与游戏无关，**不要**把它当作真实模板。
