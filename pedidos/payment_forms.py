from django import forms

from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference"]

        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Monto del abono",
                }
            ),
            "reference": forms.TextInput(
                attrs={"placeholder": "Número de comprobante (opcional)"}
            ),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise forms.ValidationError(
                "El monto debe ser mayor que cero."
            )

        return amount
