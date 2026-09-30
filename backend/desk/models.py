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


class ToolPrefixPreset(models.Model):
    """命名的字头筛查预设：一点切换后由后台按 prefix 重新拉数。"""

    name = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=32)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="tool_prefix_presets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name}（字头 {self.prefix}）"


class PresetChangeLog(models.Model):
    """预设改动流水。预设可删，但流水只能追加，任何人不得抹除。"""

    class Action(models.TextChoices):
        CREATE = "create", "新建"
        DELETE = "delete", "删除"

    # 预设删除后仍保留痕迹：冗余快照，不设指向预设表的外键。
    preset_id = models.BigIntegerField()
    preset_name = models.CharField(max_length=64)
    prefix = models.CharField(max_length=32)
    action = models.CharField(max_length=16, choices=Action.choices)
    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="preset_change_logs",
    )
    actor_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.get_action_display()}预设 {self.preset_name}"
