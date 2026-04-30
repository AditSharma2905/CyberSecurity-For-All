from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomSignupForm(UserCreationForm):
    dob = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date of Birth",
        help_text="Used to ensure age-appropriate privacy settings."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ("email",)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            user.profile.dob = self.cleaned_data.get("dob")
            user.profile.save()
        return user
