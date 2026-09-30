from django.conf import settings
from django.db import transaction
from django.utils import timezone

from desk.models import OffsetSubmission, PresetChangeLog, ScreenPreset, User


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


def create_preset(*, user: User, name: str, tool_prefix: str) -> ScreenPreset:
    """新建命名预设并同事务记入改动流水。"""
    with transaction.atomic():
        preset = ScreenPreset.objects.create(
            name=name,
            tool_prefix=tool_prefix,
            created_by=user,
        )
        PresetChangeLog.objects.create(
            action=PresetChangeLog.Action.CREATE,
            preset_name=preset.name,
            tool_prefix=preset.tool_prefix,
            actor=user,
        )
    return preset


def delete_preset(*, user: User, preset: ScreenPreset) -> None:
    """删除预设并同事务记入改动流水；仅限创建人本人。"""
    if preset.created_by_id != user.pk:
        raise PermissionError("只能删除自己创建的预设，不能抹掉别人的预设")
    with transaction.atomic():
        PresetChangeLog.objects.create(
            action=PresetChangeLog.Action.DELETE,
            preset_name=preset.name,
            tool_prefix=preset.tool_prefix,
            actor=user,
        )
        preset.delete()
