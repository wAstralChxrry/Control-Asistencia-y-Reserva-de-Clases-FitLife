import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def favicon(request):
    destino = "/favicon.svg"
    if settings.S3_RECURSOS_BUCKET:
        try:
            cliente = boto3.client("s3", region_name=settings.S3_RECURSOS_REGION)
            destino = cliente.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_RECURSOS_BUCKET, "Key": "favicon.svg"},
                ExpiresIn=300,
            )
        except (BotoCoreError, ClientError):
            logger.exception("No fue posible obtener el favicon de S3.")
    respuesta = HttpResponseRedirect(destino)
    respuesta["Cache-Control"] = "no-store"
    return respuesta
