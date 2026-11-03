# cronport

**One schedule, every runtime.**

cronport explains a cron expression in plain language, converts it between
seven scheduler dialects, and warns you about the ways a schedule can
silently mean something *different* from what you meant.

[![CI](https://github.com/ZhuYijing316/cronport/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuYijing316/cronport/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cronport.svg)](https://pypi.org/project/cronport/)
[![Python](https://img.shields.io/pypi/pyversions/cronport.svg)](https://pypi.org/project/cronport/)
[![License](https://img.shields.io/pypi/l/cronport.svg)](https://github.com/ZhuYijing316/cronport/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/cronport.svg)](https://pypistats.org/packages/cronport)

```console
$ cronport explain "0 9 * * 1-5"

  At 09:00 on Monday to Friday
  weekdays at 09:00
```

![cronport in action](assets/demo.gif)

> Also available in Chinese: [README.zh-CN.md](README.zh-CN.md)

---

## The problem

A cron expression looks the same everywhere and means something slightly
different everywhere.

You wrote `0 9 * * 1-5` on your laptop, where the timezone is
`Asia/Shanghai`. You are moving it to GitHub Actions. It now runs at **1am
in London**, because GitHub Actions evaluates schedules in UTC and offers no
way to change that.

None of the tools that exist today will tell you that. They will happily
print `0 9 * * 1-5` back at you.

Here is what actually differs between the schedulers you are likely to use:

| Target | Fields | Timezone | The catch |
| --- | --- | --- | --- |
| **cron** | 5 | the machine's | No timezone field at all |
| **systemd** | `OnCalendar=` | system, or pinned | Completely different syntax |
| **Kubernetes** | 5 | UTC unless `spec.timeZone` | Needs Kubernetes 1.27+ for timezones |
| **GitHub Actions** | 5 | **always UTC** | No timezone setting, minimum 5 minute interval |
| **AWS EventBridge** | 6 | UTC, or `scheduleExpressionTimezone` | One of the two day fields **must** be `?` |
| **Quartz** | 6 or 7 | the JVM's | Has seconds, and ANDs its two day fields |
| **GCP Cloud Scheduler** | 5 | UTC unless `timeZone` | — |

And then there is the one that bites everybody:

> When a cron expression restricts **both** the day-of-month and the
> day-of-week, the schedule fires when **either** matches. Not both.
>
> `0 0 13 * 5` means "the 13th of the month **or** any Friday" — not "the
> 13th, if it is a Friday". It runs a dozen more times a month than most
> people expect.

cronport knows all of this, and it says so.

## Install

```console
$ pipx install cronport      # or: pip install cronport
```

No dependencies beyond the Python standard library. Python 3.9 or newer.

## Use it

```console
$ cronport explain "0 9 * * 1-5"
```

```
  At 09:00 on Monday to Friday
  weekdays at 09:00

  Field breakdown
  ┌──────────────┬───────┬────────────────────────┐
  │ field        │ value │ meaning                │
  ├──────────────┼───────┼────────────────────────┤
  │ minute       │ 0     │ minute 0               │
  │ hour         │ 9     │ 09:00                  │
  │ day-of-month │ *     │ every day of the month │
  │ month        │ *     │ every month            │
  │ day-of-week  │ 1-5   │ on Monday to Friday    │
  └──────────────┴───────┴────────────────────────┘
```

```console
$ cronport convert "0 9 * * 1-5"
```

```
  Converted · from cron

  ┌─────────────────┬─────────────────────────┬────────────────────┐
  │ target          │ expression              │ note               │
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
      day-of-month and day-of-week are both restricted, so the schedule fires
      when EITHER of them matches (OR), not when both match (AND)
      hint: if you really mean 'both', cron cannot express it -- use Quartz,
             or split the schedule into two rules

  ⚠ utc-only
      GitHub Actions evaluates schedules in UTC and offers no timezone
      setting, so this schedule does not run at your local time
      hint: convert the time yourself: local time minus your UTC offset
```

Every command takes `--json` if you want to pipe the result somewhere, and
`--lang zh` (or `--lang both`) to read it in Chinese.

## What it does

| Command | What it gives you |
| --- | --- |
| `cronport explain` | The schedule in plain language, field by field |
| `cronport next` | When it runs next, in your timezone, DST included |
| `cronport prev` | When it ran last |
| `cronport convert` | The same schedule in every other dialect |
| `cronport lint` | The ways this schedule can go wrong |
| `cronport diff` | Whether two schedules fire at exactly the same times |
| `cronport presets` | Ready made schedules for common jobs |
| `cronport dialects` | The list of supported schedulers |

### It gets daylight saving time right

Cron fires on **wall clock** time, which means some wall clock times do not
exist and some happen twice. cronport knows the difference:

```console
$ cronport next "30 2 * * *" -n 3 --tz America/New_York
```

```
  Next runs · America/New_York
  2026-03-07 02:30  Saturday
  2026-03-09 02:30  Monday        <- 02:30 does not exist on the 8th
  2026-03-10 02:30  Tuesday
```

In November, when the clock goes back, `01:30` happens twice — and cronport
tells you so.

### It compares schedules for real

Not "are the strings the same" but "do these fire at exactly the same
instants":

```console
$ cronport diff "0 9 * * 1-5" "0 9 * * 1,2,3,4,5"
  ✓ both schedules fire at exactly the same times

$ cronport diff "0 0 13 * 5" "0 0 13 * *"
  ✗ the schedules fire at different times
```

### It works as a library

```python
from cronport import CronExpression, convert, lint

schedule = CronExpression.parse("0 9 * * 1-5")

print(schedule.next_runs(3, tz="Asia/Shanghai"))
print(convert(schedule, "systemd").expression)
# Mon..Fri *-*-* 09:00:00

for issue in lint(schedule, ):
    print(issue.severity, issue.rule_id, issue.message_en)
```

## The linter

Each rule describes a way a schedule can end up meaning something other than
what its author intended.

| Rule | What it catches |
| --- | --- |
| `never-fires` | The schedule can never match a real date (`0 0 30 2 *`) |
| `dom-dow-or` | Both day fields restricted, so they are ORed, not ANDed |
| `step-not-even` | A step that does not divide the range evenly (`*/7` drifts) |
| `sub-five-minutes` | Faster than GitHub Actions guarantees |
| `utc-only` | The target runs in UTC and cannot be told otherwise |
| `seconds-unsupported` | The target has no seconds field |
| `macro-not-portable` | `@daily` does not work everywhere |
| `every-minute` | 1440 runs a day |
| `short-month` | The 29th to 31st do not exist in every month |
| `leap-day` | February 29th only happens every four years |
| `top-of-hour` | Everybody schedules at `:00`, so everybody queues at `:00` |
| `no-timezone` | Nothing pins the timezone down |

Rules are a plain list of functions, so you can add your own:

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

## Use it in CI

`cronport lint` exits with `3` when it finds an error, so a schedule that can
never fire can stop a deploy:

```yaml
- name: Check the schedule
  run: cronport lint "$CRON_EXPRESSION" --target github-actions --strict
```

## Documentation

- [Dialects](docs/dialects.md) — every target, its syntax and its rules
- [Examples](docs/examples.md) — real schedules and what they mean
- [Chinese documentation](README.zh-CN.md)

## Contributing

Contributions are welcome, including the ones that are usually hard:
new dialects, new lint rules and bug reports with a real schedule attached.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
