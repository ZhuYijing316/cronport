# Contributing to cronport

Thanks for taking the time. This document covers everything you need to go
from an idea to a merged pull request.

## The five minute setup

```console
$ git clone https://github.com/__GITHUB_USER__/cronport.git
$ cd cronport
$ python -m venv .venv && source .venv/bin/activate
$ pip install -e ".[dev]"
$ make check
```

`make check` runs the linter, the type checker and the tests. If that passes,
you are ready.

You do not need the virtualenv if you only want to run the tests — the suite
uses nothing but the standard library:

```console
$ PYTHONPATH=src python -m unittest discover -s tests
```

## What we are looking for

The most useful contributions, in rough order of how much they help:

1. **A dialect that is missing.** systemd, Kubernetes, GitHub Actions, AWS
   EventBridge, Quartz and Cloud Scheduler are covered. Airflow, Jenkins,
   systemd-run timers, GitLab CI and Elastic Schedulers are not. Open an
   issue first if you are not sure how a target should be modelled — the
   interesting part is usually the *rules*, not the syntax.
2. **A lint rule.** Every rule describes a way a schedule can end up meaning
   something other than what its author intended. If you have been bitten by
   one, that is a rule.
3. **A bug with a real schedule attached.** "The output is wrong" is hard to
   act on; "here is the expression, here is what I expected" is not.
4. **Documentation and translations.** The Chinese README exists because
   somebody asked for it. Another language would be welcome too.

## Style

- Python 3.9 compatible, fully type annotated, standard library only.
- `make format` applies ruff's formatting; the CI only lints, so formatting
  differences never fail the build.
- Docstrings on public functions, in the same voice as the rest of the code.
- Every new behaviour needs a test. Every new rule needs a test that shows
  it firing *and* a test that shows it staying quiet.
- Keep the zero dependency promise. It is the reason people can install
  cronport in a locked down environment.

## Adding a dialect

A dialect is a class with two methods.

```python
from cronport.dialects.base import Conversion, Dialect, Note

class MyDialect(Dialect):
    name = "my-dialect"
    label = "My scheduler"
    aliases = ("mine",)

    def render(self, expr, *, tz=None):
        notes = []
        if expr.has_seconds:
            notes.append(Note("warning", "This target has no seconds field."))
        return Conversion(self.name, "0 9 * * 1-5", notes)

    def parse(self, text):
        return CronExpression.parse(text, dialect="cron")
```

Register it in `src/cronport/dialects/__init__.py`, add it to `cron_like.py`
or give it its own module, and add tests in `tests/test_dialects.py`.

The hard part is not the syntax, it is the *rules*: what does the target do
with the two day fields, with the timezone, with seconds? Put what you learn
in the notes, because that is the part users cannot look up.

## Adding a lint rule

```python
def _rule_my_check(expr, ctx):
    if <something is wrong>:
        return Issue(
            rule_id="my-rule",
            severity="warning",
            message_en="What is wrong, in English.",
            message_zh="中文说明。",
            hint_en="What to do about it.",
            hint_zh="怎么解决。",
        )
    return None
```

Register it in `RULES`. Both languages are required — a rule that only has an
English message will be noticed.

## Pull requests

- One change per pull request.
- Write the description for someone who has not read the code: what changed,
  why, and how you tested it.
- CI has to be green. The `labeler` workflow will tag your pull request, and
  a maintainer will look at it.

## Reporting a bug

Use the issue template and include the schedule that misbehaves. If
`cronport lint` already flags it, that is the fastest possible fix and we
will point you at it.

## Code of conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
