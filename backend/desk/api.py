from datetime import datetime
from typing import Optional

from django.http import HttpRequest
from ninja import NinjaAPI, Query, Schema
from ninja.errors import HttpError

from desk.auth_utils import bearer_auth, create_access_token, verify_password
from desk.models import OffsetSubmission, PresetChangeLog, ToolPrefixPreset, User
from desk.services import (
    PresetPermissionError,
    create_preset,
    delete_preset,
)

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


class ListQuery(Schema):
    # 字头筛查条件：命中表与列表查询同源，过滤只在服务端做。
    tool_prefix: Optional[str] = None


class PresetIn(Schema):
    name: str
    prefix: str


class PresetOut(Schema):
    id: int
    name: str
    prefix: str
    created_by: str
    owned_by_me: bool
    created_at: datetime


class PresetLogOut(Schema):
    id: int
    preset_id: int
    preset_name: str
    prefix: str
    action: str
    actor_name: str
    created_at: datetime


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


def _filtered_submissions(tool_prefix: Optional[str]):
    """专页命中表与列表查询的唯一取数口径，禁止前端藏行。"""
    qs = OffsetSubmission.objects.all()
    if tool_prefix and tool_prefix.strip():
        qs = qs.filter(tool_code__startswith=tool_prefix.strip())
    return qs[:200]


@api.get("/submissions", response=list[SubmissionOut], auth=bearer_auth)
def list_submissions(request: HttpRequest, filters: ListQuery = Query(...)):
    rows = _filtered_submissions(filters.tool_prefix)
    return [_to_out(r) for r in rows]


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
    user: User = request.auth
    rows = ToolPrefixPreset.objects.select_related("created_by").all()
    return [
        PresetOut(
            id=r.id,
            name=r.name,
            prefix=r.prefix,
            created_by=r.created_by.username,
            owned_by_me=r.created_by_id == user.pk,
            created_at=r.created_at,
        )
        for r in rows
    ]


@api.post("/presets", response=PresetOut, auth=bearer_auth)
def create_named_preset(request: HttpRequest, body: PresetIn):
    # 操作员与复核员登录后均可新建命名预设。
    user: User = request.auth
    try:
        preset = create_preset(name=body.name, prefix=body.prefix, actor=user)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    return PresetOut(
        id=preset.id,
        name=preset.name,
        prefix=preset.prefix,
        created_by=user.username,
        owned_by_me=True,
        created_at=preset.created_at,
    )


@api.delete("/presets/{preset_id}", auth=bearer_auth)
def remove_preset(request: HttpRequest, preset_id: int):
    user: User = request.auth
    try:
        delete_preset(preset_id=preset_id, actor=user)
    except PresetPermissionError as exc:
        raise HttpError(403, str(exc))
    except ValueError as exc:
        raise HttpError(404, str(exc))
    return {"deleted": preset_id}


@api.get("/preset-logs", response=list[PresetLogOut], auth=bearer_auth)
def list_preset_logs(request: HttpRequest):
    rows = PresetChangeLog.objects.all()[:200]
    return [
        PresetLogOut(
            id=r.id,
            preset_id=r.preset_id,
            preset_name=r.preset_name,
            prefix=r.prefix,
            action=r.action,
            actor_name=r.actor_name,
            created_at=r.created_at,
        )
        for r in rows
    ]
