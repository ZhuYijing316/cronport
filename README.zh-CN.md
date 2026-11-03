# cronport

**同一份调度，所有运行时。**

cronport 用人话解释 cron 表达式，把它在七种调度器方言之间互相转换，
并且提醒你那些「看起来对、其实跑歪了」的坑。

[![CI](https://github.com/ZhuYijing316/cronport/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuYijing316/cronport/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cronport.svg)](https://pypi.org/project/cronport/)
[![Python](https://img.shields.io/pypi/pyversions/cronport.svg)](https://pypi.org/project/cronport/)
[![License](https://img.shields.io/pypi/l/cronport.svg)](https://github.com/ZhuYijing316/cronport/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/cronport.svg)](https://pypistats.org/packages/cronport)

```console
$ cronport explain "0 9 * * 1-5"

  周一至周五 09:00
  工作日 09:00
```

![cronport 实际运行效果](assets/demo.gif)

> English version: [README.md](README.md)

---

## 问题在哪

cron 表达式到处长得一样，意思却到处不太一样。

你在自己电脑上（时区 `Asia/Shanghai`）写好了 `0 9 * * 1-5`，
现在要搬到 GitHub Actions 上。

它变成了**伦敦时间凌晨 1 点**运行 —— 因为 GitHub Actions 固定按 UTC 计算，
而且没有任何办法改。

现有的工具没有一个会告诉你这件事。它们只会高高兴兴地把 `0 9 * * 1-5`
原样打印给你。

下面是你大概率会用到的调度器之间的真实差异：

| 目标 | 字段 | 时区 | 坑 |
| --- | --- | --- | --- |
| **cron** | 5 个 | 机器的 | 压根没有时区字段 |
| **systemd** | `OnCalendar=` | 系统时区或指定 | 语法跟 cron 完全不同 |
| **Kubernetes** | 5 个 | 默认 UTC，除非设 `spec.timeZone` | 时区功能需要 1.27+ |
| **GitHub Actions** | 5 个 | **永远是 UTC** | 无法设置时区，最短间隔 5 分钟 |
| **AWS EventBridge** | 6 个 | UTC，或 `scheduleExpressionTimezone` | 两个「日」字段**必须**有一个填 `?` |
| **Quartz** | 6 或 7 个 | JVM 的 | 有秒字段，且两个「日」字段是「且」的关系 |
| **GCP Cloud Scheduler** | 5 个 | 默认 UTC，除非设 `timeZone` | — |

还有那个坑倒所有人的：

> 当一个 cron 表达式**同时**限定了「日」和「星期」时，
> 触发条件是满足**任意一个**，而不是同时满足。
>
> `0 0 13 * 5` 的意思是「每月 13 号**或**任意一个周五」，
> 而不是「13 号，且恰好是周五」。它一个月会多跑十几次。

cronport 知道这些，并且会明确告诉你。

## 安装

```console
$ pipx install cronport      # 或者：pip install cronport
```

除 Python 标准库外零依赖，Python 3.9 及以上。

## 怎么用

```console
$ cronport explain "0 9 * * 1-5"
```

```
  周一至周五 09:00
  工作日 09:00

  字段拆解
  ┌──────────────┬───────┬────────────────────────┐
  │ 字段         │ 取值  │ 含义                   │
  ├──────────────┼───────┼────────────────────────┤
  │ minute       │ 0     │ 第 0 分钟              │
  │ hour         │ 9     │ 09 点                  │
  │ day-of-month │ *     │ 每月的每一天           │
  │ month        │ *     │ 每月                   │
  │ day-of-week  │ 1-5   │ 周一至周五             │
  └──────────────┴───────┴────────────────────────┘
```

```console
$ cronport convert "0 9 * * 1-5"
```

```
  转换结果 · 源 cron

  ┌─────────────────┬─────────────────────────┬────────────────────┐
  │ 目标            │ 表达式                  │ 说明               │
  ├─────────────────┼─────────────────────────┼────────────────────┤
  │ cron            │ 0 9 * * 1-5             │                    │
  │ systemd         │ Mon..Fri *-*-* 09:00:00 │                    │
  │ kubernetes      │ 0 9 * * 1-5             │                    │
  │ github-actions  │ 0 9 * * 1-5             │ ⚠ warning          │
  │ aws-eventbridge │ cron(0 9 ? * 1-5 *)     │                    │
  │ quartz          │ 0 0 9 ? * 1-5 *         │                    │
  │ gcp-scheduler   │ 0 9 * * 1-5             │                    │
  └─────────────────┴─────────────────────────┴────────────────────┘
```

```console
$ cronport lint "0 0 13 * 5" --target github-actions
```

```
  ⚠ dom-dow-or
      「日」和「星期」同时被限定，触发条件是满足任意一个（OR），而不是同时满足（AND）
      hint: 如果确实需要「同时满足」，cron 无法表达——请改用 Quartz，或拆成两条规则

  ⚠ utc-only
      GitHub Actions 的调度固定按 UTC 计算且没有时区设置，
      因此它不会在你所在的本地时间触发
      hint: 请自行换算时间：本地时间减去你的 UTC 偏移
```

所有命令都支持 `--json`（输出机器可读格式），
以及 `--lang zh` / `--lang both` / `--lang en`（切换语言）。

## 它能做什么

| 命令 | 给你什么 |
| --- | --- |
| `cronport explain` | 用人话解释调度，逐字段拆解 |
| `cronport next` | 接下来几次什么时候跑，含时区与夏令时 |
| `cronport prev` | 上一次是什么时候跑的 |
| `cronport convert` | 同一份调度在其他方言下的样子 |
| `cronport lint` | 这份调度可能在哪里出问题 |
| `cronport diff` | 两份调度是不是真的完全等价 |
| `cronport presets` | 常用调度的现成模板 |
| `cronport dialects` | 支持的调度器列表 |

### 夏令时算得对

cron 是按**墙钟时间**触发的，所以有些墙钟时间根本不存在，
有些会出现两次。cronport 知道区别：

```console
$ cronport next "30 2 * * *" -n 3 --tz America/New_York
```

```
  接下来运行 · America/New_York
  2026-03-07 02:30  周六
  2026-03-09 02:30  周一        ← 3 月 8 日没有 02:30
  2026-03-10 02:30  周二
```

十一月时钟拨回的时候，`01:30` 会出现两次 —— cronport 会告诉你。

### 真的在做等价比较

不是「两串字面量一样吗」，而是「这两个触发时刻集合完全相同吗」：

```console
$ cronport diff "0 9 * * 1-5" "0 9 * * 1,2,3,4,5"
  ✓ 两个调度的触发时刻完全相同

$ cronport diff "0 0 13 * 5" "0 0 13 * *"
  ✗ 两个调度的触发时刻不同
```

### 也能当库用

```python
from cronport import CronExpression, convert, lint

schedule = CronExpression.parse("0 9 * * 1-5")

print(schedule.next_runs(3, tz="Asia/Shanghai"))
print(convert(schedule, "systemd").expression)
# Mon..Fri *-*-* 09:00:00

for issue in lint(schedule):
    print(issue.severity, issue.rule_id, issue.message_zh)
```

## 检查规则

每一条规则都对应一种「调度含义和作者本意不一致」的方式。

| 规则 | 抓什么 |
| --- | --- |
| `never-fires` | 永远不会触发（`0 0 30 2 *`） |
| `dom-dow-or` | 两个「日」字段同时被限定，走的是「或」不是「且」 |
| `step-not-even` | 步长无法整除范围（`*/7` 会漂移） |
| `sub-five-minutes` | 比 GitHub Actions 保证的间隔还密 |
| `utc-only` | 目标固定 UTC 且无法更改 |
| `seconds-unsupported` | 目标没有秒字段 |
| `macro-not-portable` | `@daily` 不是到处都能用 |
| `every-minute` | 一天跑 1440 次 |
| `short-month` | 29~31 号并非每个月都有 |
| `leap-day` | 2 月 29 日四年才一次 |
| `top-of-hour` | 大家都卡在整点，整点就排队 |
| `no-timezone` | 没有任何地方钉死时区 |

规则就是一个普通函数列表，你可以自己加：

```python
from cronport.lint import Rule, RULES, lint

RULES.append(Rule(
    id="my-rule",
    severity="warning",
    title_en="My rule",
    title_zh="我的规则",
    check=lambda expr, ctx: None,
))
```

## 用在 CI 里

`cronport lint` 发现 error 时退出码是 `3`，
所以一个根本不会触发的调度可以直接挡住发布：

```yaml
- name: 检查调度表达式
  run: cronport lint "$CRON_EXPRESSION" --target github-actions --strict
```

## 文档

- [各方言详解](docs/dialects.md)
- [实战示例](docs/examples.md)
- [English documentation](README.md)

## 参与贡献

欢迎贡献，尤其欢迎那些通常比较难做的：
新方言、新检查规则，以及带着真实调度表达式来的 issue。
详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
