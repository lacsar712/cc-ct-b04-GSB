from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        MACHINIST = "machinist", "操作员"
        AUDITOR = "auditor", "复核员"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MACHINIST,
    )

    @property
    def can_write(self) -> bool:
        return self.role == self.Role.MACHINIST


class OffsetSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待复核"
        PROCESSING = "processing", "复核中"
        DONE = "done", "已完成"

    class Verdict(models.TextChoices):
        PASS = "合格", "合格"
        FAIL = "超差", "超差"

    tool_code = models.CharField(max_length=32, db_index=True)
    offset_um = models.IntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    verdict = models.CharField(
        max_length=8,
        choices=Verdict.choices,
        blank=True,
        default="",
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.tool_code} {self.offset_um}µm"


class ScreenPreset(models.Model):
    """按刀号字头筛查的命名预设，存后台，可点名切换。"""

    name = models.CharField(max_length=40, unique=True)
    tool_prefix = models.CharField(max_length=32)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="screen_presets",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return f"{self.name}（字头 {self.tool_prefix}）"


class PresetChangeLog(models.Model):
    """预设改动流水：名称与字头做快照留存，删预设后痕迹仍在。"""

    class Action(models.TextChoices):
        CREATE = "create", "新建"
        DELETE = "delete", "删除"

    action = models.CharField(max_length=8, choices=Action.choices)
    preset_name = models.CharField(max_length=40)
    tool_prefix = models.CharField(max_length=32)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preset_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.preset_name}"
