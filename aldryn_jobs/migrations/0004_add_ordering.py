from __future__ import absolute_import, unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aldryn_jobs', '0003_auto_20160714_1512'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobopening',
            name='ordering',
            field=models.IntegerField(verbose_name='ordering', default=0),
        ),
    ]
