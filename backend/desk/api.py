from datetime import datetime
from typing import Optional

from django.http import HttpRequest
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from desk.auth_utils import bearer_auth, create_access_token, verify_password
from desk.models import OffsetSubmission, PresetChangeLog, ScreenPreset, User
from desk.services import create_preset, delete_preset

api = NinjaAPI(title="数控刀补复核台", version="1.0")


class HealthOut(Schema):
    status: str


class LoginIn(Schema):
    username: str
    password: str


class LoginOut(Schema):
    token: str
    username: str
    role: str
    can_write: bool


class SubmissionIn(Schema):
    tool_code: str
    offset_um: int


class SubmissionOut(Schema):
    id: int
    tool_code: str
    offset_um: int
    status: str
    verdict: str
    created_at: datetime
    reviewed_at: Optional[datetime]


class PresetIn(Schema):
    name: str
    tool_prefix: str


class PresetOut(Schema):
    id: int
    name: str
    tool_prefix: str
    created_by: str
    created_at: datetime


class PresetLogOut(Schema):
    id: int
    action: str
    preset_name: str
    tool_prefix: str
    actor: str
    created_at: datetime


class OkOut(Schema):
    ok: bool


def _to_out(row: OffsetSubmission) -> SubmissionOut:
    return SubmissionOut(
        id=row.id,
        tool_code=row.tool_code,
        offset_um=row.offset_um,
        status=row.status,
        verdict=row.verdict or "",
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def _preset_to_out(preset: ScreenPreset) -> PresetOut:
    return PresetOut(
        id=preset.id,
        name=preset.name,
        tool_prefix=preset.tool_prefix,
        created_by=preset.created_by.username if preset.created_by else "",
        created_at=preset.created_at,
    )


def _log_to_out(log: PresetChangeLog) -> PresetLogOut:
    return PresetLogOut(
        id=log.id,
        action=log.action,
        preset_name=log.preset_name,
        tool_prefix=log.tool_prefix,
        actor=log.actor.username if log.actor else "",
        created_at=log.created_at,
    )


@api.get("/health", response=HealthOut)
def health(request: HttpRequest):
    return {"status": "ok"}


@api.post("/auth/login", response=LoginOut)
def login(request: HttpRequest, body: LoginIn):
    try:
        user = User.objects.get(username=body.username)
    except User.DoesNotExist:
        raise HttpError(401, "用户名或密码错误")
    if not verify_password(body.password, user.password):
        raise HttpError(401, "用户名或密码错误")
    token = create_access_token(user)
    return {
        "token": token,
        "username": user.username,
        "role": user.role,
        "can_write": user.can_write,
    }


@api.get("/submissions", response=list[SubmissionOut], auth=bearer_auth)
def list_submissions(request: HttpRequest, tool_prefix: Optional[str] = None):
    """复核列表与筛查台命中表共用的唯一查询入口。

    传 tool_prefix 时由服务端按刀具编号字头过滤；不传或为空则回整表。
    """
    qs = OffsetSubmission.objects.all()
    prefix = (tool_prefix or "").strip()
    if prefix:
        qs = qs.filter(tool_code__startswith=prefix)
    return [_to_out(r) for r in qs[:200]]


@api.get("/submissions/{submission_id}", response=SubmissionOut, auth=bearer_auth)
def get_submission(request: HttpRequest, submission_id: int):
    try:
        row = OffsetSubmission.objects.get(pk=submission_id)
    except OffsetSubmission.DoesNotExist:
        raise HttpError(404, "刀补记录不存在")
    return _to_out(row)


@api.post("/submissions", response=SubmissionOut, auth=bearer_auth)
def create_submission(request: HttpRequest, body: SubmissionIn):
    user: User = request.auth
    if not user.can_write:
        raise HttpError(403, "当前账号只读，不能提交刀补")
    tool_code = body.tool_code.strip()
    if not tool_code:
        raise HttpError(400, "刀具编号不能为空")
    row = OffsetSubmission.objects.create(
        tool_code=tool_code,
        offset_um=body.offset_um,
        submitted_by=user,
        status=OffsetSubmission.Status.PENDING,
    )
    return _to_out(row)


@api.get("/presets", response=list[PresetOut], auth=bearer_auth)
def list_presets(request: HttpRequest):
    presets = ScreenPreset.objects.select_related("created_by").all()
    return [_preset_to_out(p) for p in presets]


@api.post("/presets", response=PresetOut, auth=bearer_auth)
def create_preset_endpoint(request: HttpRequest, body: PresetIn):
    """操作员与复核员都可新建命名预设。"""
    name = body.name.strip()
    tool_prefix = body.tool_prefix.strip()
    if not name:
        raise HttpError(400, "预设称呼不能为空")
    if not tool_prefix:
        raise HttpError(400, "筛查字头不能为空")
    if ScreenPreset.objects.filter(name=name).exists():
        raise HttpError(409, "预设称呼已存在，请换一个名字")
    preset = create_preset(user=request.auth, name=name, tool_prefix=tool_prefix)
    return _preset_to_out(preset)


@api.delete("/presets/{preset_id}", response=OkOut, auth=bearer_auth)
def delete_preset_endpoint(request: HttpRequest, preset_id: int):
    try:
        preset = ScreenPreset.objects.get(pk=preset_id)
    except ScreenPreset.DoesNotExist:
        raise HttpError(404, "预设不存在")
    try:
        delete_preset(user=request.auth, preset=preset)
    except PermissionError as exc:
        raise HttpError(403, str(exc))
    return {"ok": True}


@api.get("/preset-logs", response=list[PresetLogOut], auth=bearer_auth)
def list_preset_logs(request: HttpRequest):
    logs = PresetChangeLog.objects.select_related("actor").all()[:200]
    return [_log_to_out(log) for log in logs]
