"""A small library of schedules people actually use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Preset:
    """A named schedule."""

    key: str
    expression: str
    title_en: str
    title_zh: str
    category: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "expression": self.expression,
            "title": {"en": self.title_en, "zh": self.title_zh},
            "category": self.category,
        }


PRESETS: List[Preset] = [
    Preset("every-minute", "* * * * *", "Every minute", "每分钟", "frequent"),
    Preset("every-5-minutes", "*/5 * * * *", "Every 5 minutes", "每 5 分钟", "frequent"),
    Preset("every-15-minutes", "*/15 * * * *", "Every 15 minutes", "每 15 分钟", "frequent"),
    Preset("every-30-minutes", "*/30 * * * *", "Every 30 minutes", "每 30 分钟", "frequent"),
    Preset("hourly", "0 * * * *", "Every hour on the hour", "每整点", "frequent"),
    Preset("every-2-hours", "0 */2 * * *", "Every 2 hours", "每 2 小时", "frequent"),
    Preset("every-6-hours", "0 */6 * * *", "Every 6 hours", "每 6 小时", "frequent"),
    Preset("daily-midnight", "0 0 * * *", "Every day at midnight", "每天午夜", "daily"),
    Preset("daily-3am", "0 3 * * *", "Every day at 03:00", "每天 03:00", "daily"),
    Preset("daily-9am", "0 9 * * *", "Every day at 09:00", "每天 09:00", "daily"),
    Preset("daily-noon", "0 12 * * *", "Every day at noon", "每天中午", "daily"),
    Preset("daily-midnight-and-noon", "0 0,12 * * *", "Twice a day", "每天两次（午夜和中午）", "daily"),
    Preset("weekdays-9am", "0 9 * * 1-5", "Weekdays at 09:00", "工作日 09:00", "weekly"),
    Preset("weekends-10am", "0 10 * * 6,0", "Weekends at 10:00", "周末 10:00", "weekly"),
    Preset("monday-9am", "0 9 * * 1", "Every Monday at 09:00", "每周一 09:00", "weekly"),
    Preset("sunday-midnight", "0 0 * * 0", "Every Sunday at midnight", "每周日午夜", "weekly"),
    Preset("monthly-1st", "0 0 1 * *", "First day of the month", "每月 1 号", "monthly"),
    Preset("monthly-15th", "0 0 15 * *", "Fifteenth day of the month", "每月 15 号", "monthly"),
    Preset("quarterly", "0 0 1 1,4,7,10 *", "First day of each quarter", "每季度第一天", "seasonal"),
    Preset("yearly", "0 0 1 1 *", "First of January", "每年 1 月 1 日", "seasonal"),
    Preset(
        "hourly-weekdays-9-to-17",
        "0 9-17 * * 1-5",
        "Every hour, weekdays 09:00-17:00",
        "工作日 9-17 点每小时",
        "maintenance",
    ),
    Preset("nightly-backup", "30 2 * * *", "Nightly backup at 02:30", "每晚 02:30 备份", "maintenance"),
    Preset("weekly-backup", "0 3 * * 0", "Weekly backup on Sunday", "每周日备份", "maintenance"),
    Preset("cert-renewal", "0 4 1 * *", "Certificate renewal check", "证书续期检查", "maintenance"),
]

BY_KEY: Dict[str, Preset] = {preset.key: preset for preset in PRESETS}


def list_presets(category: Optional[str] = None) -> List[Preset]:
    """Every preset, optionally filtered by category."""
    if category is None:
        return list(PRESETS)
    return [preset for preset in PRESETS if preset.category == category]


def get_preset(key: str) -> Optional[Preset]:
    """Look up one preset by key."""
    return BY_KEY.get(key)


def categories() -> List[str]:
    """The categories used by the presets, in a stable order."""
    seen: List[str] = []
    for preset in PRESETS:
        if preset.category not in seen:
            seen.append(preset.category)
    return seen
