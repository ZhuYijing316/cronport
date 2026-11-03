# Examples

Real schedules, what they mean, and what cronport has to say about them.

---

## Every weekday at 09:00

```console
$ cronport explain "0 9 * * 1-5"
```

```
  At 09:00 on Monday to Friday
  weekdays at 09:00
```

The one people write most often. It behaves the same everywhere, except for
the timezone: on GitHub Actions it fires at 01:00 UTC.

---

## Every 15 minutes

```console
$ cronport explain "*/15 * * * *"
```

```
  Every 15 minutes, every day
```

Fifteen divides sixty, so the interval is exact. `*/7` does not:

```console
$ cronport lint "*/7 * * * *"
```

```
  ⚠ step-not-even
      the step 7 does not divide the 60 minute values evenly, so the interval
      is not uniform: the last firing of a minute is only 4 minute(s) before
      the cycle starts again
```

`*/7` fires at :00, :07, :14 ... :56 and then four minutes later at :00
again. If a seven minute cadence matters, use a scheduler with real interval
support.

---

## The 13th of the month, but only on Fridays

```console
$ cronport explain "0 0 13 * 5"
```

```
  At 00:00 on the 13th of the month or on Friday
```

Read that again. It is **or**, not **and**. The schedule fires on every
Friday *and* on every 13th, whether or not the 13th is a Friday.

The linter says so:

```console
$ cronport lint "0 0 13 * 5"
```

```
  ⚠ dom-dow-or
      day-of-month and day-of-week are both restricted, so the schedule fires
      when EITHER of them matches (OR), not when both match (AND)
      hint: if you really mean 'both', cron cannot express it -- use Quartz,
             or split the schedule into two rules
```

To get the *and* behaviour, convert to Quartz:

```console
$ cronport convert "0 0 13 * 5" --to quartz
```

```
  0 0 0 13 * 5 *
```

---

## February 29th

```console
$ cronport next "0 0 29 2 *" -n 3
```

```
  2028-02-29  Wednesday
  2032-02-29  Monday
  2036-02-29  Thursday
```

Four years apart. If your monitoring expects a yearly run, it will report a
false alarm three years out of four.

---

## The 30th of February

```console
$ cronport lint "0 0 30 2 *"
```

```
  ✗ never-fires
      this schedule can never fire: the day-of-month values do not exist in
      the selected months
```

An error, not a warning. The schedule will never run.

---

## 09:00 in my timezone, on GitHub Actions

The Actions scheduler is UTC only, so the time has to be converted by hand:

```console
$ cronport next "0 9 * * 1-5" --tz Asia/Shanghai -n 1
```

```
  2026-11-04 09:00  Wednesday
```

which is `2026-11-04 01:00 UTC`, so the workflow needs:

```yaml
on:
  schedule:
    - cron: "0 1 * * 1-5"
```

---

## A schedule that only exists once a year

```console
$ cronport explain "0 0 1 1 *"
```

```
  At 00:00 on the 1st of the month in January
  yearly on the 1st
```

---

## Checking that two schedules are the same

```console
$ cronport diff "0 9 * * 1-5" "0 9 * * 1,2,3,4,5"
```

```
  ✓ both schedules fire at exactly the same times
```

```console
$ cronport diff "0 9 * * *" "0 9 * * 0-6"
```

```
  ✓ both schedules fire at exactly the same times
```

The second pair looks different but both fire every day. cronport compares
the actual firing sets, not the text.
