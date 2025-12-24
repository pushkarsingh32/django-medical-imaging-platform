from django import forms
from .models import Reservervation


class ReservationForm(forms.ModelForm):
    class Meta: 
        model = Reservervation
        # fields = ['first_name', 'last_name', 'guest_count', 'comments']
        fields = '__all__'

