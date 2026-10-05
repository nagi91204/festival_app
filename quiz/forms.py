from django import forms

from .models import Question


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = (
            "title", "question_type", "category", "difficulty", "body",
            "choice_1", "choice_2", "choice_3", "choice_4", "correct_choice",
            "correct_text", "explanation", "image", "audio_file", "points", "is_active",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "例：日本の首都"}),
            "category": forms.TextInput(attrs={"placeholder": "例：アニメ、音楽、この声のキャラクターは？"}),
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "例：日本の首都はどこでしょう？"}),
            "choice_1": forms.TextInput(attrs={"placeholder": "例：東京"}),
            "choice_2": forms.TextInput(attrs={"placeholder": "例：大阪"}),
            "choice_3": forms.TextInput(attrs={"placeholder": "例：京都"}),
            "choice_4": forms.TextInput(attrs={"placeholder": "例：名古屋"}),
            "correct_choice": forms.NumberInput(attrs={"min": 1, "max": 4, "placeholder": "例：1"}),
            "correct_text": forms.TextInput(attrs={"placeholder": "例：東京"}),
            "explanation": forms.Textarea(attrs={"rows": 3, "placeholder": "例：日本の首都は東京都です。"}),
            "points": forms.NumberInput(attrs={"min": 0, "placeholder": "例：10"}),
        }
