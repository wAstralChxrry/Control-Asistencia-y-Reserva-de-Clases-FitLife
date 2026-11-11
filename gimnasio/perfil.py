from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from .permisos import solo_socio


class PerfilForm(forms.ModelForm):
    class Meta:
        from django.contrib.auth.models import User

        model = User
        fields = ("first_name", "last_name", "email")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
        }


@solo_socio
def editar_perfil(request):
    form = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tus datos se actualizaron correctamente.")
        return redirect("perfil")
    return render(request, "gimnasio/perfil.html", {"form": form})


@solo_socio
def cambiar_contrasena(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Tu contraseña se actualizó correctamente.")
        return redirect("perfil")
    return render(request, "gimnasio/contrasena.html", {"form": form})
