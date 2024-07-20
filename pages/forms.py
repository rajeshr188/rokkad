from django import forms


class MaxxFileUploadForm(forms.Form):
    model_choices = (
        ("Payment", "Payment"),
        ("Receipt", "Receipt"),
        ("Purchase", "Purchase"),
        ("Sales", "Sales"),
        ("Debtors", "Debtors"),
        ("Creditors", "Creditors"),
    )
    model = forms.ChoiceField(choices=model_choices)
    file = forms.FileField(label="Select a file")
