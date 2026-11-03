# The dialects

Every target cronport can speak, its syntax, and the rules that make it
different from plain cron.

---

## cron

The original. Five fields, in this order:

```
minute  hour  day-of-month  month  day-of-week
 0-59   0-23      1-31       1-12      0-6
```

* Sunday is `0` and `7`.
* Month and weekday accept three letter names: `jan`, `mon`.
* `@yearly`, `@annually`, `@monthly`, `@weekly`, `@daily`, `@midnight` and
  `@hourly` are shorthands.
* **No timezone field.** The schedule follows the timezone of the machine it
  runs on, which is why the same crontab on two servers can mean two
  different moments.
* No seconds field.

### The day-of-month / day-of-week rule

If **both** the day-of-month and the day-of-week are restricted (that is,
neither is written as `*`), the schedule fires when **either** matches.

```
0 0 13 * 5      the 13th of the month OR any Friday
0 0 13 * *      only the 13th
0 0 * * 5       only every Friday
```

Writing `1-31` instead of `*` also counts as "restricted", which is why
cronport never quietly rewrites one into the other.

---

## systemd

`OnCalendar=` in a `.timer` unit. The shape is:

```
[DayOfWeek] Year-Month-Day Hour:Minute:Second
```

Every part is optional, and `*`, lists (`Mon,Thu`), ranges (`Mon..Fri`),
steps (`*:0/15`) and shorthands (`daily`, `hourly`, `weekly`, `monthly`,
`quarterly`, `yearly`) all work.

```ini
[Timer]
OnCalendar=Mon..Fri *-*-* 09:00:00
Persistent=true
```

### How it differs from cron

| | cron | systemd |
| --- | --- | --- |
| Timezone | the machine's | system, or pinned at the end of the value |
| Two day fields | OR | **AND** |
| Several lines | not a thing | **OR** between them |
| Seconds | no | yes |

So a cron schedule that restricts both day fields needs **two**
`OnCalendar=` lines to keep its meaning, and cronport emits both:

```ini
OnCalendar=*-*-13 00:00:00
OnCalendar=Fri *-*-* 00:00:00
```

A timezone can be pinned directly:

```ini
OnCalendar=*-*-* 09:00:00 Asia/Shanghai
```

Validate any value before you ship it:

```console
$ systemd-analyze calendar "Mon..Fri *-*-* 09:00:00"
```

---

## Kubernetes

A CronJob's `spec.schedule` is the same five field cron syntax.

```yaml
apiVersion: batch/v1
kind: CronJob
spec:
  schedule: "0 9 * * 1-5"
  timeZone: Asia/Shanghai   # needs Kubernetes 1.27+
```

* The timezone defaults to **UTC**. Set `spec.timeZone` to change it.
* The day-of-month / day-of-week rule is the same OR rule as cron.
* No seconds field.

---

## GitHub Actions

```yaml
on:
  schedule:
    - cron: "0 9 * * 1-5"
```

* **Always UTC.** There is no timezone setting and no way to add one. If you
  want 09:00 in `Asia/Shanghai`, write `0 1 * * 1-5`.
* Five fields, no seconds.
* GitHub only guarantees that scheduled workflows run at least every **five
  minutes**, and they can be delayed during peak load — especially on the
  hour.
* `@macros` do not work.

---

## AWS EventBridge

Rules and EventBridge Scheduler jobs take a Quartz style `cron(...)` with six
fields.

```
cron(minute hour day-of-month month day-of-week year)
```

```json
{
  "ScheduleExpression": "cron(0 9 ? * 1-5 *)"
}
```

* One of the two day fields **must** be `?`. AWS rejects an expression where
  both are given.
* There is no seconds field.
* EventBridge rules run in UTC. EventBridge Scheduler can pin one with
  `scheduleExpressionTimezone`.
* Because AWS cannot OR two day fields, a cron schedule that restricts both
  needs **two rules**.

---

## Quartz

Six or seven fields, used by Java schedulers (Spring's `@Scheduled`, Quartz
itself).

```
second  minute  hour  day-of-month  month  day-of-week  [year]
```

```
0 0 9 ? * 1-5 *
```

* The two day fields are combined with **AND**, not OR.
* `?` means "this field does not matter".
* Quartz adds `L` (last day), `W` (nearest weekday) and `#` (nth weekday),
  which cronport does not produce.

---

## Google Cloud Scheduler

```console
$ gcloud scheduler jobs create http my-job \
    --schedule="0 9 * * 1-5" \
    --time-zone="Asia/Shanghai"
```

Five field cron syntax, UTC by default, `timeZone` to change it.

---

## Converting between them

```console
$ cronport convert "0 9 * * 1-5" --to systemd
$ cronport convert "0 9 * * 1-5" --from systemd --to cron
```

The source dialects cronport can read are `cron`, `systemd`,
`aws-eventbridge` and `quartz`.

Every conversion comes with **notes** explaining anything that changed on the
way: a dropped seconds field, a timezone the target cannot express, a
schedule that has to be split across two rules.
