from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BalanceForm, DynamicQuestionsForm, FeedbackForm, GoalForm
from .models import Course, CourseModule, LearnerProfile, MaterialFeedback, ModuleElement, WebSearchProfile
from .services.pipeline import CoursePipeline, UserGoal


def index(request):
    form = GoalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        goal = form.cleaned_data["goal"].strip()
        try:
            questions = CoursePipeline().ask_profile_questions(goal)
        except Exception as exc:
            messages.error(request, f"Не удалось получить уточняющие вопросы от LLM: {exc}")
            return render(request, "learning/index.html", {"form": form})

        if not questions:
            messages.error(request, "LLM не вернула уточняющие вопросы. Проверьте промпт и настройки модели.")
            return render(request, "learning/index.html", {"form": form})

        request.session["course_goal"] = goal
        request.session["profile_questions"] = questions
        request.session.modified = True
        return redirect("learning:questions")

    return render(request, "learning/index.html", {"form": form})


def questions(request):
    goal = request.session.get("course_goal")
    questions_payload = request.session.get("profile_questions") or []
    if not goal or not questions_payload:
        return redirect("learning:index")

    form = DynamicQuestionsForm(request.POST or None, questions=questions_payload)
    if request.method == "POST" and form.is_valid():
        answers = {key: value for key, value in form.cleaned_data.items()}
        learner = _get_or_create_learner(request)
        user_goal = UserGoal(
            goal=goal,
            current_level=answers.get("level", ""),
            target_level=answers.get("target_level", ""),
            preferred_formats=_preferred_formats(answers),
            constraints={"questions": questions_payload, "answers": answers},
        )
        try:
            course = CoursePipeline().build_course_from_goal(learner, user_goal)
        except Exception as exc:
            messages.error(request, f"Не удалось построить курс через LLM/web_search: {exc}")
            return render(request, "learning/questions.html", {"form": form, "goal": goal})

        messages.success(request, "Курс построен и сохранён в админке.")
        return redirect("learning:course_detail", pk=course.pk)

    return render(request, "learning/questions.html", {"form": form, "goal": goal})


def course_detail(request, pk):
    course = get_object_or_404(
        Course.objects.prefetch_related(
            Prefetch(
                "modules",
                queryset=CourseModule.objects.prefetch_related(
                    Prefetch("elements", queryset=ModuleElement.objects.select_related("material").order_by("order"))
                ).order_by("order"),
            )
        ),
        pk=pk,
    )
    return render(
        request,
        "learning/course_detail.html",
        {
            "course": course,
            "feedback_form": FeedbackForm(),
            "balance_form": BalanceForm(),
        },
    )


@require_POST
def element_feedback(request, pk):
    element = get_object_or_404(ModuleElement.objects.select_related("module__course", "material"), pk=pk)
    form = FeedbackForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверьте форму обратной связи.")
        return redirect("learning:course_detail", pk=element.module.course_id)

    feedback = MaterialFeedback.objects.create(
        learner=element.module.course.learner,
        element=element,
        rating=form.cleaned_data["rating"],
        replacement_kind=form.cleaned_data["replacement_kind"],
        comment=form.cleaned_data["comment"],
    )
    if feedback.replacement_requested:
        try:
            replacement = CoursePipeline().replace_element_material(feedback)
        except Exception as exc:
            messages.error(request, f"Фидбек сохранён, но замена через web_search не удалась: {exc}")
            return redirect("learning:course_detail", pk=element.module.course_id)
        if replacement:
            messages.success(request, "Материал заменён через web_search и LLM-структурирование.")
        else:
            messages.warning(request, "Новые кандидаты найдены, но LLM не выбрала подходящую замену.")
    else:
        messages.success(request, "Фидбек сохранён.")
    return redirect("learning:course_detail", pk=element.module.course_id)


@require_POST
def module_skip(request, pk):
    module = get_object_or_404(CourseModule, pk=pk)
    module.status = CourseModule.Status.SKIPPED
    module.save(update_fields=["status", "updated_at"])
    messages.success(request, "Модуль пропущен.")
    return redirect("learning:course_detail", pk=module.course_id)


@require_POST
def module_balance(request, pk):
    module = get_object_or_404(CourseModule, pk=pk)
    form = BalanceForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Не удалось понять тип корректировки.")
        return redirect("learning:course_detail", pk=module.course_id)

    material_kind = form.cleaned_data["balance"]
    module.content_balance = "Больше видео" if material_kind == WebSearchProfile.MaterialKind.VIDEO else "Больше статей"
    module.status = CourseModule.Status.NEEDS_ADJUSTMENT
    module.save(update_fields=["content_balance", "status", "updated_at"])
    try:
        pipeline = CoursePipeline()
        pipeline.search_module_materials(module, material_kind)
        pipeline.structure_module_materials(module)
    except Exception as exc:
        messages.error(request, f"Корректировка сохранена, но перестроение материалов не удалось: {exc}")
        return redirect("learning:course_detail", pk=module.course_id)

    messages.success(request, "Модуль перестроен с новым балансом материалов.")
    return redirect("learning:course_detail", pk=module.course_id)


def _get_or_create_learner(request):
    if request.user.is_authenticated:
        learner, _ = LearnerProfile.objects.get_or_create(
            user=request.user,
            defaults={"display_name": request.user.get_username()},
        )
        return learner

    learner_id = request.session.get("learner_id")
    if learner_id:
        learner = LearnerProfile.objects.filter(pk=learner_id).first()
        if learner:
            return learner

    learner = LearnerProfile.objects.create(display_name="Пользователь mini app")
    request.session["learner_id"] = learner.id
    request.session.modified = True
    return learner


def _preferred_formats(answers: dict) -> list[str]:
    text = " ".join(answers.values()).lower()
    formats = []
    if "видео" in text:
        formats.append("video")
    if "стат" in text or "текст" in text or "докум" in text:
        formats.append("text")
    if "практи" in text:
        formats.append("practice")
    return formats
