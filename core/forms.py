from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomSignupForm(UserCreationForm):
    # We add the dob field here so Django knows to look for it
    dob = forms.DateField(
        required=True, 
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date of Birth",
        help_text="Used strictly to ensure age-appropriate privacy settings."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',) # Adding email is usually good practice too

    def save(self, commit=True):
        # Save the user first
        user = super().save(commit=False)
        if commit:
            user.save()
            # The signal in models.py automatically created the profile.
            # Now we update it with the DoB.
            user.profile.dob = self.cleaned_data.get('dob')
            
            # GDPR check: If you want to wipe it for users under 15, 
            # you could do that math here before saving.
            user.profile.save()
        return user