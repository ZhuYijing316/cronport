# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | ✅ |

## Reporting a vulnerability

Please **do not** open a public issue for a security problem.

Instead, email the maintainer or use GitHub's private vulnerability reporting
on the Security tab of the repository. You will get an acknowledgement within
72 hours and an assessment within a week.

## What counts as a vulnerability here

cronport parses untrusted input, so the interesting problems are:

- a crash or an unbounded loop when parsing a hostile expression
- a quadratic blow-up that makes the CLI unusable
- a schedule that cronport reports as safe but is not

A schedule that cronport's linter fails to flag is a bug, but it is a
correctness bug rather than a security vulnerability unless it can be turned
into a denial of service.

## What is not a vulnerability

- cronport says a schedule is fine and the schedule turns out to be wrong
  because *the schedule* was wrong. Use `cronport lint`.
- A timezone database is out of date on your machine.
