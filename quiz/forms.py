from django import forms
from django.core.exceptions import ValidationError

from .models import Question

AUDIO_EXTENSIONS = ("mp3", "m4a", "wav", "ogg")
VIDEO_EXTENSIONS = ("mp4", "webm", "mov")


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = (
            "title", "question_type", "category", "body",
            "choice_1", "choice_2", "choice_3", "choice_4", "correct_choice",
            "correct_text", "explanation", "image", "audio_file", "video_file", "points", "is_active",
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
            "audio_file": forms.ClearableFileInput(attrs={"accept": "audio/*"}),
            "video_file": forms.ClearableFileInput(attrs={"accept": "video/mp4,video/webm,video/quicktime"}),
        }

    def clean_audio_file(self):
        return self._validate_media_extension(self.cleaned_data.get("audio_file"), AUDIO_EXTENSIONS, "音声")

    def clean_video_file(self):
        return self._validate_media_extension(self.cleaned_data.get("video_file"), VIDEO_EXTENSIONS, "動画")

    @staticmethod
    def _validate_media_extension(uploaded, allowed_extensions, label):
        if not uploaded:
            return uploaded
        extension = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
        if extension not in allowed_extensions:
            raise ValidationError(f"{label}ファイルは {'・'.join(allowed_extensions)} のいずれかの形式で登録してください。")
        return uploaded
