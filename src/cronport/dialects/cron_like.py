"""The cron family of dialects.

These four targets all speak (almost) the same five field language, so they
share an implementation.  What differs is not the syntax but the *rules*
around it, and those differences are exactly what cronport exists to show:

* GitHub Actions always runs in UTC and has no timezone setting at all.
* Kubernetes runs in UTC unless ``spec.timeZone`` says otherwise.
* Plain cron follows the timezone of the machine it runs on.
"""

from __future__ import annotations

from typing import List, Optional

from ..expr import CronExpression
from .base import (
    LEVEL_INFO,
    LEVEL_WARNING,
    Conversion,
    Dialect,
    Note,
    dom_dow_note,
)


def minimum_gap_minutes(expr: CronExpression) -> Optional[int]:
    """The shortest gap between two firings, in minutes.

    Returns ``None`` when the schedule is not dense enough to have a
    meaningful gap (for example ``0 9 * * *``).
    """
    minutes = expr.minute.sorted_values()
    hours = expr.hour.sorted_values()
    if not minutes or not hours:
        return None
    if len(minutes) > 1:
        return min(minutes[index + 1] - minutes[index] for index in range(len(minutes) - 1))
    if len(hours) > 1:
        return min((60 - minutes[-1]) + minutes[0], 24 * 60)
    return 24 * 60


class CronDialect(Dialect):
    """Plain Vixie/Posix cron, the one everybody knows."""

    name = "cron"
    label = "Standard cron (Vixie/cronie)"
    aliases = ("crontab", "posix", "unix", "linux")
    supports_macros = True

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        if expr.has_seconds:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "standard cron has no seconds field; the seconds part was dropped",
                    "标准 cron 没有秒字段，秒部分已被丢弃",
                )
            )
        if tz:
            notes.append(
                Note(
                    LEVEL_INFO,
                    f"cron has no timezone field; this schedule follows the machine's "
                    f"local timezone ({tz} cannot be expressed here)",
                    f"cron 没有时区字段：该调度跟随机器的本地时区（此处无法表达 {tz}）",
                )
            )
        note = dom_dow_note(expr)
        if note:
            notes.append(note)
        return Conversion(self.name, self._cron_fields(expr), notes)

    def parse(self, text: str) -> CronExpression:
        return CronExpression.parse(text, dialect="cron")


class KubernetesDialect(Dialect):
    """Kubernetes CronJob ``spec.schedule``."""

    name = "kubernetes"
    label = "Kubernetes CronJob"
    aliases = ("k8s", "kube", "cronjob")
    supports_timezone = True

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        extras = {}
        if expr.has_seconds:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "CronJob has no seconds field; the seconds part was dropped",
                    "CronJob 没有秒字段，秒部分已被丢弃",
                )
            )
        if tz:
            extras["timeZone"] = tz
            notes.append(
                Note(
                    LEVEL_INFO,
                    "CronJob runs in UTC unless spec.timeZone is set "
                    "(needs Kubernetes 1.27 or newer)",
                    "CronJob 默认使用 UTC，需要 Kubernetes 1.27 及以上并设置 spec.timeZone",
                )
            )
        note = dom_dow_note(expr)
        if note:
            notes.append(note)
        return Conversion(self.name, self._cron_fields(expr), notes, extras)

    def parse(self, text: str) -> CronExpression:
        return CronExpression.parse(text, dialect="cron")


class GitHubActionsDialect(Dialect):
    """GitHub Actions ``on.schedule``."""

    name = "github-actions"
    label = "GitHub Actions workflow schedule"
    aliases = ("gh-actions", "actions", "github")

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        if expr.has_seconds:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "GitHub Actions schedules have no seconds field; the seconds part was dropped",
                    "GitHub Actions 的 schedule 没有秒字段，秒部分已被丢弃",
                )
            )
        notes.append(
            Note(
                LEVEL_WARNING,
                "GitHub Actions always evaluates schedules in UTC and has no timezone "
                "setting, so this schedule fires at a different local time than you may expect",
                "GitHub Actions 的调度固定按 UTC 计算，且没有时区设置，"
                "因此实际触发时刻和本地时间可能对不上",
            )
        )
        gap = minimum_gap_minutes(expr)
        if gap is not None and gap < 5:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    f"this schedule fires roughly every {gap} minute(s); GitHub Actions "
                    "only guarantees that scheduled workflows run at least every 5 minutes "
                    "and may be delayed during peak load",
                    f"该调度约每 {gap} 分钟触发一次；GitHub Actions 只保证调度间隔不短于 5 分钟，"
                    "高峰期还可能被延迟",
                )
            )
        note = dom_dow_note(expr)
        if note:
            notes.append(note)
        return Conversion(self.name, self._cron_fields(expr), notes)

    def parse(self, text: str) -> CronExpression:
        return CronExpression.parse(text, dialect="cron")


class GcpSchedulerDialect(Dialect):
    """Google Cloud Scheduler."""

    name = "gcp-scheduler"
    label = "Google Cloud Scheduler"
    aliases = ("gcp", "google", "cloud-scheduler")
    supports_timezone = True

    def render(self, expr: CronExpression, *, tz: Optional[str] = None) -> Conversion:
        notes: List[Note] = []
        extras = {}
        if expr.has_seconds:
            notes.append(
                Note(
                    LEVEL_WARNING,
                    "Cloud Scheduler has no seconds field; the seconds part was dropped",
                    "Cloud Scheduler 没有秒字段，秒部分已被丢弃",
                )
            )
        if tz:
            extras["timeZone"] = tz
            notes.append(
                Note(
                    LEVEL_INFO,
                    "Cloud Scheduler defaults to UTC; set the timeZone field to use "
                    f"{tz} instead",
                    f"Cloud Scheduler 默认为 UTC，需要设置 timeZone 字段才能使用 {tz}",
                )
            )
        note = dom_dow_note(expr)
        if note:
            notes.append(note)
        return Conversion(self.name, self._cron_fields(expr), notes, extras)

    def parse(self, text: str) -> CronExpression:
        return CronExpression.parse(text, dialect="cron")
