"""Renovación JWT con comprobación del estado y contraseña del usuario."""

from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password
from rest_framework_simplejwt.views import TokenRefreshView


class RenovacionSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        usuario_id = token.payload.get(api_settings.USER_ID_CLAIM)
        usuario = (
            get_user_model()
            .objects.filter(**{api_settings.USER_ID_FIELD: usuario_id})
            .first()
        )
        if not usuario or not api_settings.USER_AUTHENTICATION_RULE(usuario):
            raise AuthenticationFailed("La cuenta ya no está disponible.")
        if api_settings.CHECK_REVOKE_TOKEN:
            huella = token.payload.get(api_settings.REVOKE_TOKEN_CLAIM, "")
            if not constant_time_compare(
                huella, get_md5_hash_password(usuario.password)
            ):
                raise AuthenticationFailed("La sesión ya no es válida.")
        try:
            return super().validate(attrs)
        except get_user_model().DoesNotExist as exc:
            raise AuthenticationFailed("La cuenta ya no está disponible.") from exc


class RenovacionView(TokenRefreshView):
    serializer_class = RenovacionSerializer
