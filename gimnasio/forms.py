from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .fechas import fecha_fin_membresia
from .models import Plan, Membresia, Pago, Clase


class SocioForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña", widget=forms.PasswordInput, required=False
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ModelForm asigna el valor del campo al objeto durante la validación.
        self._password_original = self.instance.password if self.instance.pk else None
        self.fields["password"].help_text = (
            "Deja este campo vacío para conservar la contraseña actual."
            if self.instance.pk
            else "La contraseña debe cumplir las reglas de seguridad."
        )

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not password:
            if not self.instance.pk:
                raise forms.ValidationError("Ingresa una contraseña para el socio.")
            return password

        # Validar con los datos introducidos, también al crear un socio nuevo.
        user = User(
            username=self.cleaned_data.get("username", ""),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
            email=self.cleaned_data.get("email", ""),
        )
        validate_password(password, user=user)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data["password"]:
            user.set_password(self.cleaned_data["password"])
        else:
            user.password = self._password_original
        if commit:
            user.save()
        return user


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = "__all__"


class MembresiaForm(forms.ModelForm):
    class Meta:
        model = Membresia
        fields = ["socio", "plan", "inicio", "fin", "estado"]
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and "fin" in self.fields:
            self.fields["fin"].required = False
            self.fields["fin"].help_text = (
                "Si se deja vacío, se calcula según los meses del plan."
            )
        if "socio" not in self.fields:
            return
        if self.instance.pk:
            self.fields["socio"].disabled = True
            self.fields["socio"].help_text = (
                "El titular no puede cambiarse después de crear la membresía."
            )
        else:
            self.fields["socio"].queryset = User.objects.filter(is_staff=False)

    def clean(self):
        data = super().clean()
        if (
            not self.instance.pk
            and not data.get("fin")
            and data.get("inicio")
            and data.get("plan")
        ):
            try:
                data["fin"] = fecha_fin_membresia(
                    data["inicio"], data["plan"].duracion_meses
                )
            except (OverflowError, ValueError):
                self.add_error(
                    "inicio", "La duración del plan excede las fechas permitidas."
                )
        if data.get("inicio") and data.get("fin") and data["fin"] < data["inicio"]:
            raise forms.ValidationError("La fecha final debe ser posterior al inicio.")
        return data


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = "__all__"
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}


class ClaseForm(forms.ModelForm):
    class Meta:
        model = Clase
        fields = "__all__"
        widgets = {
            "inicio": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            )
        }

    def clean_cupos(self):
        cupos = self.cleaned_data["cupos"]
        if cupos < 1:
            raise forms.ValidationError("La clase debe tener al menos un cupo.")
        if (
            self.instance.pk
            and cupos < self.instance.reservas.filter(espera=False).count()
        ):
            raise forms.ValidationError(
                "Los cupos no pueden ser menores que las reservas confirmadas."
            )
        return cupos

    def clean_inicio(self):
        inicio = self.cleaned_data["inicio"]
        if self.instance.pk and inicio != self.instance.inicio:
            from .models import Reserva
            from .servicios import clase_fuera_vigencia

            socios = self.instance.reservas.values("socio_id")
            if (
                Reserva.objects.filter(socio_id__in=socios, clase__inicio=inicio)
                .exclude(clase=self.instance)
                .exists()
            ):
                raise forms.ValidationError(
                    "Un socio ya está inscrito en otra clase a esa hora."
                )
            if clase_fuera_vigencia(self.instance, inicio):
                raise forms.ValidationError(
                    "Hay socios cuya membresía no cubre la nueva fecha de la clase."
                )
        return inicio
