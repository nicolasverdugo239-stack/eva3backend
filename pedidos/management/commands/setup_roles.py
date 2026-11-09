from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from pedidos.roles import ADMINISTRATORS, DISPATCH, KITCHEN, SALES, WAREHOUSE


class Command(BaseCommand):
    help = "Crea los grupos de acceso para los roles de Dulce Arte."

    def handle(self, *args, **options):
        for name in (ADMINISTRATORS, SALES, KITCHEN, WAREHOUSE, DISPATCH):
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Roles creados: Administradores, Ventas, Cocina, Bodega y Despacho."))
