# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-03

The first release.

### Added

- `cronport explain` — describe a schedule in plain language, in English or
  Chinese, field by field.
- `cronport next` / `cronport prev` — the run times around now, with correct
  handling of daylight saving time: wall clock times that do not exist are
  skipped, and times that happen twice are reported twice.
- `cronport convert` — convert a schedule between cron, systemd,
  Kubernetes CronJob, GitHub Actions, AWS EventBridge, Quartz and Google
  Cloud Scheduler.
- `cronport lint` — twelve rules that catch the ways a schedule can silently
  mean something other than what its author intended.
- `cronport diff` — compare two schedules by when they actually fire, not by
  how their text looks.
- `cronport presets` — a library of schedules people actually use.
- `cronport dialects` — the list of supported schedulers.
- `--json` output for every command, for scripting and for CI.
- `--lang en`, `--lang zh` and `--lang both`.
- A Python API: `CronExpression`, `convert`, `lint`, `explain`.

[Unreleased]: https://github.com/__GITHUB_USER__/cronport/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/__GITHUB_USER__/cronport/releases/tag/v0.1.0
