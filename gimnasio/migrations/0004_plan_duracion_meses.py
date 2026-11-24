from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def convertir_a_meses(apps, schema_editor):
    plan = apps.get_model("gimnasio", "Plan")
    datos = plan.objects.using(schema_editor.connection.alias)
    invalidos = [
        pk
        for pk, dias in datos.values_list("pk", "duracion_meses").iterator()
        if dias < 30 or dias % 30 or dias > 36000
    ]
    if invalidos:
        raise ValueError(
            "No se pueden convertir automáticamente los planes con duración inválida "
            "o días no múltiplos de 30: " + ", ".join(map(str, invalidos))
        )
    for registro in datos.all().iterator():
        registro.duracion_meses //= 30
        registro.save(
            update_fields=["duracion_meses"], using=schema_editor.connection.alias
        )


def convertir_a_dias(apps, schema_editor):
    plan = apps.get_model("gimnasio", "Plan")
    datos = plan.objects.using(schema_editor.connection.alias)
    for registro in datos.all().iterator():
        registro.duracion_meses *= 30
        registro.save(
            update_fields=["duracion_meses"], using=schema_editor.connection.alias
        )


class Migration(migrations.Migration):
    dependencies = [("gimnasio", "0003_lotedemo")]

    operations = [
        migrations.RenameField(
            model_name="plan", old_name="duracion_dias", new_name="duracion_meses"
        ),
        migrations.RunPython(convertir_a_meses, convertir_a_dias),
        migrations.AlterField(
            model_name="plan",
            name="duracion_meses",
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1), MaxValueValidator(1200)],
                verbose_name="duración en meses",
            ),
        ),
    ]
