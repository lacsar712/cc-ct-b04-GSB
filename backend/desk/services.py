from django.conf import settings
from django.db import transaction
from django.utils import timezone

from desk.models import OffsetSubmission, PresetChangeLog, ToolPrefixPreset, User


class PresetPermissionError(Exception):
    """操作人无权操作该预设（如复核员抹别人的预设）。"""


def evaluate_verdict(offset_um: int) -> str:
    if abs(offset_um) <= settings.OFFSET_TOLERANCE_UM:
        return OffsetSubmission.Verdict.PASS
    return OffsetSubmission.Verdict.FAIL


def apply_verdict(submission: OffsetSubmission) -> None:
    submission.verdict = evaluate_verdict(submission.offset_um)
    submission.status = OffsetSubmission.Status.DONE
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=["verdict", "status", "reviewed_at"],
    )


@transaction.atomic
def create_preset(*, name: str, prefix: str, actor: User) -> ToolPrefixPreset:
    name = name.strip()
    prefix = prefix.strip()
    if not name:
        raise ValueError("预设称呼不能为空")
    if not prefix:
        raise ValueError("字头不能为空")
    if ToolPrefixPreset.objects.filter(name=name).exists():
        raise ValueError(f"预设称呼「{name}」已存在")

    preset = ToolPrefixPreset.objects.create(
        name=name,
        prefix=prefix,
        created_by=actor,
    )
    PresetChangeLog.objects.create(
        preset_id=preset.pk,
        preset_name=preset.name,
        prefix=preset.prefix,
        action=PresetChangeLog.Action.CREATE,
        actor=actor,
        actor_name=actor.username,
    )
    return preset


@transaction.atomic
def delete_preset(*, preset_id: int, actor: User) -> ToolPrefixPreset:
    """删除预设并在同一事务内补删除流水。

    流水写入失败则预设删除一并回滚；只允许预设创建人删除自己的预设。
    """
    try:
        preset = ToolPrefixPreset.objects.select_for_update().get(pk=preset_id)
    except ToolPrefixPreset.DoesNotExist:
        raise ValueError("预设不存在")

    if preset.created_by_id != actor.pk:
        raise PresetPermissionError("只能删除自己新建的预设，不得抹掉别人的预设")

    PresetChangeLog.objects.create(
        preset_id=preset.pk,
        preset_name=preset.name,
        prefix=preset.prefix,
        action=PresetChangeLog.Action.DELETE,
        actor=actor,
        actor_name=actor.username,
    )
    preset.delete()
    return preset
