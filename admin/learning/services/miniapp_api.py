import base64
import binascii
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import mimetypes
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from learning.models import (
    Certificate,
    Course,
    CourseModule,
    LearnerProfile,
    LearningMaterial,
    MaterialFeedback,
    ModuleElement,
    WebSearchProfile,
)
from learning.services.pipeline import CoursePipeline, UserGoal


FEEDBACK_RATING_MAP = {
    "useful": MaterialFeedback.Rating.USEFUL,
    "hard": MaterialFeedback.Rating.TOO_HARD,
    "easy": MaterialFeedback.Rating.TOO_EASY,
    "replace": MaterialFeedback.Rating.UNSUITABLE,
}


@dataclass(frozen=True)
class OnboardingResult:
    learner: LearnerProfile
    course: Course


def complete_onboarding(payload: dict[str, Any]) -> OnboardingResult:
    telegram_user_id = str(payload.get("telegramUserId") or "").strip()
    if not telegram_user_id:
        raise ValueError("telegramUserId is required")

    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    raw_profile = payload.get("rawProfile") if isinstance(payload.get("rawProfile"), dict) else {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    answers = payload.get("answers") if isinstance(payload.get("answers"), list) else []

    goal = _profile_value(profile, "goal") or str(raw_profile.get("goal") or "").strip()
    interest = _profile_value(profile, "interest") or str(raw_profile.get("interest") or "").strip()
    level = _profile_value(profile, "level") or str(raw_profile.get("level") or "").strip()
    target = _profile_value(profile, "focus") or str(raw_profile.get("focus") or "").strip()
    time_value = _profile_value(profile, "time") or str(raw_profile.get("time") or "").strip()
    goal_text = goal or interest or "Персональный образовательный маршрут"

    display_name = " ".join(
        value
        for value in (user.get("firstName"), user.get("lastName"))
        if isinstance(value, str) and value.strip()
    ).strip()
    if not display_name and user.get("username"):
        display_name = f"@{user['username']}"

    learner, _ = LearnerProfile.objects.update_or_create(
        telegram_id=telegram_user_id,
        defaults={
            "display_name": display_name[:160],
            "target_roles": [interest] if interest else [],
            "learning_preferences": {
                "source": payload.get("source") or "telegram_bot",
                "schemaVersion": payload.get("schemaVersion"),
                "profile": profile,
                "rawProfile": raw_profile,
                "result": payload.get("result") or {},
                "submittedAt": payload.get("submittedAt"),
            },
        },
    )

    user_goal = UserGoal(
        goal=goal_text,
        current_level=level,
        target_level=target,
        weekly_hours=_weekly_hours(time_value),
        preferred_formats=_preferred_formats(profile, raw_profile),
        constraints={
            "telegramUserId": telegram_user_id,
            "chatId": payload.get("chatId"),
            "quizSessionId": payload.get("quizSessionId"),
            "courseSessionId": payload.get("courseSessionId"),
            "answers": answers,
            "profile": profile,
            "rawProfile": raw_profile,
        },
    )
    course = CoursePipeline().build_course_from_goal(learner, user_goal)
    course.profile_snapshot = {
        **(course.profile_snapshot or {}),
        "adminOnboardingPayload": payload,
    }
    course.save(update_fields=["profile_snapshot", "updated_at"])
    return OnboardingResult(learner=learner, course=course)


def roadmap_for_telegram_user(telegram_user_id: str | int | None) -> dict[str, Any]:
    telegram_id = str(telegram_user_id or "").strip()
    if not telegram_id:
        return empty_roadmap("telegram_user_id_required", has_completed_onboarding=False)

    learner = LearnerProfile.objects.filter(telegram_id=telegram_id).first()
    if learner is None:
        return empty_roadmap("onboarding_required", has_completed_onboarding=False)

    course = latest_course_for_learner(learner)
    if course is None:
        return empty_roadmap("route_missing", has_completed_onboarding=True, learner=learner)
    if course.status in {Course.Status.DRAFT, Course.Status.BUILDING}:
        return empty_roadmap("course_building", has_completed_onboarding=True, learner=learner, course=course)

    return serialize_course(course)


def mark_module(course_id: int, module_index: int, telegram_user_id: str | int) -> dict[str, Any]:
    module = module_for_user(course_id, module_index, telegram_user_id)
    module.status = CourseModule.Status.COMPLETED
    module.save(update_fields=["status", "updated_at"])
    update_course_progress(module.course)
    return {"ok": True, "courseId": module.course_id, "moduleIndex": module_index}


def save_feedback(
    course_id: int,
    module_index: int,
    feedback: str,
    telegram_user_id: str | int,
    *,
    comment: str = "",
    replacement_kind: str = "",
) -> dict[str, Any]:
    module = module_for_user(course_id, module_index, telegram_user_id)
    element = module.elements.select_related("material").order_by("order").first()
    if element is None:
        raise ValueError("module_has_no_elements")

    rating = FEEDBACK_RATING_MAP.get(str(feedback or "").strip(), MaterialFeedback.Rating.USEFUL)
    if replacement_kind not in {choice for choice, _ in WebSearchProfile.MaterialKind.choices}:
        replacement_kind = ""
    material_feedback = MaterialFeedback.objects.create(
        learner=module.course.learner,
        element=element,
        rating=rating,
        comment=comment,
        replacement_kind=replacement_kind,
    )

    replacement = None
    if material_feedback.replacement_requested:
        replacement = CoursePipeline().replace_element_material(material_feedback)

    return {
        "ok": True,
        "feedbackId": material_feedback.id,
        "replacementElementId": replacement.id if replacement else None,
    }


def upload_certificate(payload: dict[str, Any], telegram_user_id: str | int) -> dict[str, Any]:
    learner = LearnerProfile.objects.filter(telegram_id=str(telegram_user_id)).first()
    if learner is None:
        raise ValueError("learner_not_found")

    title = str(payload.get("title") or payload.get("fileName") or "Сертификат").strip()[:240]
    file_name = safe_file_name(str(payload.get("fileName") or title), str(payload.get("fileType") or ""))
    file_bytes = decode_data_url(str(payload.get("dataUrl") or ""))
    if len(file_bytes) > 12 * 1024 * 1024:
        raise ValueError("file_too_large")

    certificate = Certificate.objects.create(
        learner=learner,
        title=title or "Сертификат",
        issuer=str(payload.get("issuer") or "").strip()[:160],
        issued_at=parse_date(payload.get("issuedAt")),
        external_url=str(payload.get("externalUrl") or "").strip(),
        competencies=payload.get("competencies") if isinstance(payload.get("competencies"), list) else [],
    )
    certificate.file.save(file_name, ContentFile(file_bytes), save=True)
    return {"ok": True, "certificate": serialize_certificate(certificate)}


def latest_course_for_learner(learner: LearnerProfile) -> Course | None:
    return (
        Course.objects.filter(learner=learner)
        .prefetch_related(
            Prefetch(
                "modules",
                queryset=CourseModule.objects.prefetch_related(
                    Prefetch("elements", queryset=ModuleElement.objects.select_related("material").order_by("order"))
                ).order_by("order"),
            )
        )
        .order_by("-updated_at", "-id")
        .first()
    )


def module_for_user(course_id: int, module_index: int, telegram_user_id: str | int) -> CourseModule:
    telegram_id = str(telegram_user_id or "").strip()
    module_order = int(module_index) + 1
    module = (
        CourseModule.objects.select_related("course__learner")
        .filter(course_id=course_id, order=module_order, course__learner__telegram_id=telegram_id)
        .first()
    )
    if module is None:
        raise ValueError("module_not_found")
    return module


@transaction.atomic
def update_course_progress(course: Course) -> None:
    modules = list(course.modules.all())
    if not modules:
        return
    completed = sum(1 for module in modules if module.status == CourseModule.Status.COMPLETED)
    if completed >= len(modules):
        course.status = Course.Status.COMPLETED
    elif completed > 0 and course.status == Course.Status.READY:
        course.status = Course.Status.IN_PROGRESS
    course.save(update_fields=["status", "updated_at"])


def serialize_course(course: Course) -> dict[str, Any]:
    modules = [serialize_module(module, index) for index, module in enumerate(course.modules.all())]
    total = max(len(modules), 1)
    completed = sum(1 for module in modules if module["progress"] == 100)
    progress = 100 if course.status == Course.Status.COMPLETED else round(completed / total * 100)
    profile = serialize_profile(course)
    certificates = [serialize_certificate(certificate) for certificate in course.learner.certificates.all()] if course.learner else []
    return {
        "source": "django",
        "hasData": True,
        "hasCompletedOnboarding": True,
        "telegramUserId": int(course.learner.telegram_id) if course.learner and course.learner.telegram_id.isdigit() else course.learner.telegram_id if course.learner else "",
        "id": f"course-{course.id}",
        "courseId": course.id,
        "title": course.title,
        "domainTitle": profile.get("direction") or "Персональный трек",
        "explanation": course.recommendation_summary or course.goal,
        "progress": progress,
        "status": course.status,
        "profile": profile,
        "modules": modules,
        "stats": [
            {"value": str(len(modules)), "label": "модулей в персональном маршруте", "tone": "blue"},
            {"value": f"{completed}/{len(modules)}", "label": "модулей завершено", "tone": "green"},
            {"value": str(sum(len(section["topics"]) for module in modules for section in module["sections"])), "label": "тем и материалов", "tone": "pink"},
            {"value": str(len(certificates)), "label": "сертификатов загружено", "tone": "plain"},
        ],
        "certificates": certificates,
        "events": [],
        "startedAt": iso(course.created_at),
        "updatedAt": iso(course.updated_at),
    }


def serialize_module(module: CourseModule, index: int) -> dict[str, Any]:
    progress = module_progress(module)
    topic = {
        "id": f"course-{module.course_id}-topic-{index}",
        "title": module.title,
        "progress": progress,
        "status": module_status(progress),
        "description": module.description,
        "skills": module.competencies or module.learning_outcomes or ["самостоятельная практика"],
        "competency": "; ".join(module.learning_outcomes or module.competencies or []) or "После модуля появится понятный практический результат.",
        "practice": module.use_cases,
        "checkpoint": module.market_relevance,
        "moduleIndex": index,
        "courseId": module.course_id,
        "feedback": [],
        "materials": [serialize_material(element, material_index) for material_index, element in enumerate(module.elements.all())],
    }
    return {
        "id": f"course-{module.course_id}-module-{index}",
        "title": module.title,
        "goal": module.description,
        "duration": hours_label(module.total_effort_hours),
        "progress": progress,
        "status": module_status(progress),
        "sections": [
            {
                "id": f"course-{module.course_id}-section-{index}",
                "title": module.content_balance or "Материалы и практика",
                "topics": [topic],
            }
        ],
    }


def serialize_material(element: ModuleElement, index: int) -> dict[str, Any]:
    material = element.material
    material_format = material.format if material else "other"
    return {
        "id": f"element-{element.id}",
        "elementId": element.id,
        "format": material_format,
        "kind": element.get_element_type_display(),
        "title": element.title or (material.title if material else f"Материал {index + 1}"),
        "source": material.source if material else "",
        "duration": minutes_label(element.estimated_minutes or (material.estimated_minutes if material else 0)),
        "minutes": element.estimated_minutes or (material.estimated_minutes if material else 0),
        "interaction": element.recommendation_reason,
        "isFree": material.access in {LearningMaterial.Access.FREE, LearningMaterial.Access.OPEN, LearningMaterial.Access.FREEMIUM} if material else True,
        "language": material.language if material else "ru",
        "url": material.url if material else "",
        "summary": element.short_description or (material.summary if material else ""),
    }


def serialize_profile(course: Course) -> dict[str, Any]:
    snapshot = course.profile_snapshot or {}
    payload = snapshot.get("adminOnboardingPayload") if isinstance(snapshot.get("adminOnboardingPayload"), dict) else {}
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    return {
        "goal": _profile_value(profile, "goal") or course.goal,
        "direction": _profile_value(profile, "interest") or (course.learner.target_roles[0] if course.learner and course.learner.target_roles else ""),
        "age": _profile_code(profile, "age"),
        "ageLabel": _profile_value(profile, "age") or "возраст не указан",
        "experience": _profile_code(profile, "level"),
        "experienceLabel": course.initial_level or _profile_value(profile, "level") or "уровень не указан",
        "weeklyTime": _profile_code(profile, "time"),
        "weeklyTimeLabel": _profile_value(profile, "time") or "темп не указан",
        "formats": snapshot.get("preferred_formats") or ["материалы", "практика"],
        "formatsLabel": _profile_value(profile, "constraints") or "персональная подача",
        "routeMode": course.target_level or _profile_value(profile, "focus") or "персональный режим",
        "focus": _profile_value(profile, "focus") or "",
        "constraints": _profile_value(profile, "constraints") or "",
    }


def serialize_certificate(certificate: Certificate) -> dict[str, Any]:
    return {
        "id": str(certificate.id),
        "title": certificate.title,
        "file_type": mimetypes.guess_type(certificate.file.name)[0] or "application/octet-stream",
        "local_path": certificate.file.url if certificate.file else "",
        "source": "django",
        "uploaded_at": iso(certificate.created_at),
        "issuer": certificate.issuer,
        "issued_at": certificate.issued_at.isoformat() if certificate.issued_at else "",
        "external_url": certificate.external_url,
    }


def empty_roadmap(
    reason: str,
    *,
    has_completed_onboarding: bool,
    learner: LearnerProfile | None = None,
    course: Course | None = None,
) -> dict[str, Any]:
    payload = {
        "source": "django",
        "hasData": False,
        "hasCompletedOnboarding": has_completed_onboarding,
        "reason": reason,
    }
    if learner is not None:
        payload["telegramUserId"] = learner.telegram_id
        payload["user"] = {"display_name": learner.display_name, "telegram_id": learner.telegram_id}
    if course is not None:
        payload["courseId"] = course.id
        payload["status"] = course.status
    return payload


def module_progress(module: CourseModule) -> int:
    if module.status == CourseModule.Status.COMPLETED:
        return 100
    if module.status == CourseModule.Status.ACTIVE:
        return 35
    return 0


def module_status(progress: int) -> str:
    if progress == 100:
        return "completed"
    if progress > 0:
        return "current"
    return "locked"


def _profile_value(profile: dict[str, Any], key: str) -> str:
    item = profile.get(key)
    if isinstance(item, dict):
        return str(item.get("value") or item.get("tone") or "").strip()
    return ""


def _profile_code(profile: dict[str, Any], key: str) -> str:
    item = profile.get(key)
    if isinstance(item, dict):
        return str(item.get("code") or "").strip()
    return ""


def _weekly_hours(value: str) -> int | None:
    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        return None
    return max(int(digits[:2]), 1)


def _preferred_formats(profile: dict[str, Any], raw_profile: dict[str, Any]) -> list[str]:
    text = " ".join(str(value) for value in [profile, raw_profile]).lower()
    formats = []
    if "видео" in text:
        formats.append("video")
    if "стат" in text or "текст" in text or "докум" in text:
        formats.append("text")
    if "практи" in text:
        formats.append("practice")
    return formats


def decode_data_url(data_url: str) -> bytes:
    if not data_url:
        raise ValueError("dataUrl is required")
    encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        return base64.b64decode(encoded, validate=True)
    except binascii.Error as error:
        raise ValueError("invalid_data_url") from error


def safe_file_name(file_name: str, file_type: str) -> str:
    raw_name = Path(file_name).name.strip() or "certificate"
    allowed = []
    for char in raw_name:
        if char.isalnum() or char in {".", "-", "_"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("_")
    safe_name = "".join(allowed).strip("._") or "certificate"
    if "." not in safe_name:
        safe_name += mimetypes.guess_extension(file_type) or ".bin"
    return safe_name[:120]


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def hours_label(value: Decimal) -> str:
    if not value:
        return ""
    return f"{value:g} ч"


def minutes_label(value: int) -> str:
    return f"{value} мин" if value else ""


def iso(value) -> str:
    if not value:
        return ""
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value.isoformat()
