# Reply templates

Copy, change the parts in `{}`, and send. They are here so that answering a
question takes a minute rather than an hour.

---

## "How do I convert cron to Kubernetes / GitHub Actions / ...?"

> Hi there, thanks for asking!
>
> ```console
> $ cronport convert "{expression}" --to {target}
> ```
>
> {paste the output here}
>
> The note about the timezone matters: {explain it from the output}.
>
> You can also see all the other dialects at once by leaving `--to` out.

---

## "How do I run it at my local time?"

> The schedule is evaluated in UTC by {GitHub Actions / AWS EventBridge}, and
> there is no setting to change that. To run it at 09:00 in your timezone you
> need to convert the time yourself:
>
> ```console
> $ cronport next "{expression}" --tz {your timezone} -n 1
> ```
>
> That shows the UTC equivalent of your local time.

---

## "What does this expression mean?"

> ```console
> $ cronport explain "{expression}"
> ```
>
> In short: {paste the summary line}.
>
> `cronport next "{expression}" -n 5` shows you when it actually runs.

---

## "It crashes on my machine (Windows)"

> Sorry about that. cronport is installed as a command, not run as a script:
>
> ```console
> > pipx install cronport
> > cronport --version
> ```
>
> If `pipx` is not available, `pip install cronport` works too, and then
> `cronport` is on your PATH. If you still see the error, please paste the
> output of `cronport --version` and `python --version`.

---

## "Can you add support for {scheduler}?"

> Thanks, that would be a good addition.
>
> Could you share the documentation for its schedule syntax? The part I need
> most is:
>
> 1. What does a schedule look like in {scheduler}?
> 2. How does it combine a day-of-month with a day-of-week — AND or OR?
> 3. How does it handle timezones?
> 4. Does it have a seconds field?
>
> With that I can add it. It is also fine to just open a pull request — the
> guide is in CONTRIBUTING.md.

---

## "This expression is wrong / does not do what I expect"

> Run the linter on it, it usually spots this:
>
> ```console
> $ cronport lint "{expression}"
> ```
>
> {paste the output}
>
> The most common cause is that cron combines the day-of-month and the
> day-of-week with OR rather than AND, so the schedule fires more often than
> expected. `cronport diff` can also compare two expressions and tell you
> whether they fire at exactly the same times.

---

## "How do I use cronport as a library?"

> ```python
> from cronport import CronExpression, convert, lint
>
> schedule = CronExpression.parse("{expression}")
> print(schedule.next_runs(3, tz="Asia/Shanghai"))
> print(convert(schedule, "systemd").expression)
> for issue in lint(schedule):
>     print(issue.severity, issue.rule_id, issue.message_en)
> ```

---

## Closing an issue that is a duplicate

> Thanks for reporting this! It is the same as {link to the other issue}, so
> I will continue there.
