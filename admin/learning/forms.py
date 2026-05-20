from django import forms

from .models import MaterialFeedback, WebSearchProfile


class GoalForm(forms.Form):
    goal = forms.CharField(
        label="Цель обучения",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Например: хочу за 2 месяца научиться делать Django-сервисы и собрать pet-проект",
            }
        ),
    )


class DynamicQuestionsForm(forms.Form):
    def __init__(self, *args, questions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = questions or []
        for index, question in enumerate(self.questions):
            key = question.get("key") or f"question_{index + 1}"
            self.fields[key] = forms.CharField(
                label=question.get("text") or "Уточнение",
                widget=forms.Textarea(attrs={"rows": 3}),
                required=True,
            )


class FeedbackForm(forms.Form):
    rating = forms.ChoiceField(label="Оценка", choices=MaterialFeedback.Rating.choices)
    replacement_kind = forms.ChoiceField(
        label="Заменить на",
        choices=(("", "Такой же тип"),) + tuple(WebSearchProfile.MaterialKind.choices),
        required=False,
    )
    comment = forms.CharField(label="Комментарий", widget=forms.Textarea(attrs={"rows": 3}), required=False)


class BalanceForm(forms.Form):
    balance = forms.ChoiceField(
        label="Скорректировать модуль",
        choices=(
            ("video", "Больше видео"),
            ("text", "Больше статей и интерактива"),
        ),
    )
