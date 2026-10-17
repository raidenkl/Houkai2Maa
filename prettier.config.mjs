import * as multilineArrays from 'prettier-plugin-multiline-arrays'
import * as maafwSort from '@nekosu/prettier-plugin-maafw-sort'

/**
 * Prettier 配置。
 *
 * - `prettier-plugin-multiline-arrays`：数组多行展开，保持 pipeline 的可读 diff。
 * - `@nekosu/prettier-plugin-maafw-sort`：按节点生命周期顺序排序 pipeline 字段，
 *   降低无关字段顺序变化带来的 diff 噪音。两者同时提供 json 解析器，
 *   因此用 `patchPlugin` 合并（见插件 README）。
 */
export default {
    plugins: [maafwSort.patchPlugin(multilineArrays)],
    multilineArraysWrapThreshold: 1,
    tabWidth: 4,
    printWidth: 120,
    useTabs: false,
    bracketSameLine: true,
    bracketSpacing: false,
    semi: false,
    singleQuote: true,
    arrowParens: 'always',
    trailingComma: 'all',
    endOfLine: 'lf',
    overrides: [
        {
            files: [
                '**/*.yml',
                '**/*.yaml',
            ],
            options: {
                parser: 'yaml',
                tabWidth: 2,
            },
        },
        {
            files: ['*.json'],
            options: {
                parser: 'json',
                useTabs: false,
                bracketSameLine: false,
            },
        },
    ],
}
