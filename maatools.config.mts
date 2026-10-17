import {loadAllTestCases} from '@nekosu/maa-tools'
import type {FullConfig} from '@nekosu/maa-tools'

/**
 * @nekosu/maa-tools 配置。
 *
 * - `maaCache`：框架运行时缓存放在仓库内，避免污染用户主目录，
 *   也让 AI / CI 在同一目录下可复现。
 * - `check`：静态检查（任务引用、图片路径、schema 一致性等）。
 * - `test`：离线节点测试，用 `tests/node-cases/**\/*.json` 描述
 *   「截图 → 期望命中的节点」。没有截图时该步骤自动跳过。
 */
const config: FullConfig = {
    cwd: import.meta.dirname,
    // 与 tools/dev/setup.py 中 maafw 的主版本保持一致，"latest" 会跟随 beta 漂移
    maaVersion: '5.14.3',
    maaCache: '.maa-tools',
    maaStdoutLevel: 'Fatal',
    interfacePath: 'assets/interface.json',
    check: {
        override: {
            // 忽略 mpe-config 带来的报错
            // ignore warning caused by mpe-config
            // 'mpe-config': 'ignore'
        },
    },
    test: {
        casesCwd: 'tests/node-cases',
        cases: async () => {
            const [cases] = await loadAllTestCases('tests/node-cases', '*.json')
            return cases
        },
    },
}

export default config
