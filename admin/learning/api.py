import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from learning.services.miniapp_api import (
    complete_onboarding,
    mark_module,
    roadmap_for_telegram_user,
    save_feedback,
    upload_certificate,
)


class OnboardingCompleteSerializer(serializers.Serializer):
    schemaVersion = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(required=False, allow_blank=True)
    telegramUserId = serializers.IntegerField()
    chatId = serializers.IntegerField(required=False, allow_null=True)
    quizSessionId = serializers.IntegerField(required=False, allow_null=True)
    courseSessionId = serializers.IntegerField(required=False, allow_null=True)
    profile = serializers.DictField(required=False)
    rawProfile = serializers.DictField(required=False)
    answers = serializers.ListField(required=False)
    result = serializers.DictField(required=False)
    route = serializers.ListField(required=False)
    user = serializers.DictField(required=False)
    submittedAt = serializers.CharField(required=False, allow_blank=True)


class ProgressMarkSerializer(serializers.Serializer):
    courseId = serializers.IntegerField()
    moduleIndex = serializers.IntegerField(min_value=0)
    telegramUserId = serializers.IntegerField(required=False)


class FeedbackSerializer(ProgressMarkSerializer):
    feedback = serializers.CharField(required=False, allow_blank=True)
    comment = serializers.CharField(required=False, allow_blank=True)
    replacementKind = serializers.CharField(required=False, allow_blank=True)


class CertificateUploadSerializer(serializers.Serializer):
    telegramUserId = serializers.IntegerField(required=False)
    title = serializers.CharField(required=False, allow_blank=True)
    fileName = serializers.CharField(required=False, allow_blank=True)
    fileType = serializers.CharField(required=False, allow_blank=True)
    size = serializers.IntegerField(required=False, min_value=0)
    dataUrl = serializers.CharField()
    issuer = serializers.CharField(required=False, allow_blank=True)
    issuedAt = serializers.CharField(required=False, allow_blank=True)
    externalUrl = serializers.URLField(required=False, allow_blank=True)
    competencies = serializers.ListField(required=False)


class OnboardingCompleteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        auth_response = require_admin_token(request)
        if auth_response is not None:
            return auth_response

        serializer = OnboardingCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = complete_onboarding(serializer.validated_data)
        return Response(
            {
                "ok": True,
                "telegramUserId": result.learner.telegram_id,
                "courseId": result.course.id,
                "status": result.course.status,
            },
            status=status.HTTP_200_OK,
        )


class RoadmapView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        telegram_user_id = resolve_telegram_user_id(request)
        if not telegram_user_id:
            telegram_user_id = request.query_params.get("telegram_user_id") if settings.DEBUG else ""
        return Response(roadmap_for_telegram_user(telegram_user_id))


class ProgressMarkView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = ProgressMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        telegram_user_id = resolve_telegram_user_id(request, serializer.validated_data)
        if not telegram_user_id:
            return Response({"ok": False, "error": "telegram_user_id_required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = mark_module(
                serializer.validated_data["courseId"],
                serializer.validated_data["moduleIndex"],
                telegram_user_id,
            )
        except ValueError as error:
            return Response({"ok": False, "error": str(error)}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)


class FeedbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        telegram_user_id = resolve_telegram_user_id(request, serializer.validated_data)
        if not telegram_user_id:
            return Response({"ok": False, "error": "telegram_user_id_required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = save_feedback(
                serializer.validated_data["courseId"],
                serializer.validated_data["moduleIndex"],
                serializer.validated_data.get("feedback") or "useful",
                telegram_user_id,
                comment=serializer.validated_data.get("comment") or "",
                replacement_kind=serializer.validated_data.get("replacementKind") or "",
            )
        except ValueError as error:
            return Response({"ok": False, "error": str(error)}, status=status.HTTP_404_NOT_FOUND)
        return Response(result)


class CertificateUploadView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = CertificateUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        telegram_user_id = resolve_telegram_user_id(request, serializer.validated_data)
        if not telegram_user_id:
            return Response({"ok": False, "error": "telegram_user_id_required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = upload_certificate(serializer.validated_data, telegram_user_id)
        except ValueError as error:
            return Response({"ok": False, "error": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


def require_admin_token(request):
    expected = settings.ADMIN_API_TOKEN
    if not expected:
        return Response({"ok": False, "error": "admin_api_token_not_configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    header = request.headers.get("Authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not hmac.compare_digest(token, expected):
        return Response({"ok": False, "error": "unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
    return None


def resolve_telegram_user_id(request, payload=None) -> str:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        user_id = user_id_from_init_data(init_data)
        if user_id:
            return user_id
        if not settings.DEBUG:
            return ""

    if settings.DEBUG:
        payload = payload or {}
        return str(
            payload.get("telegramUserId")
            or request.query_params.get("telegram_user_id")
            or request.query_params.get("user_id")
            or ""
        ).strip()
    return ""


def user_id_from_init_data(init_data: str) -> str:
    if not settings.TELEGRAM_BOT_TOKEN:
        return ""
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        return ""
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return ""
    try:
        user = json.loads(values.get("user") or "{}")
    except json.JSONDecodeError:
        return ""
    return str(user.get("id") or "").strip()
