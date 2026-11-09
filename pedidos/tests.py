from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Customer,
    Dispatch,
    Ingredient,
    InventoryMovement,
    Order,
    OrderIngredient,
    OrderStatusHistory,
)
from .roles import DISPATCH, KITCHEN, SALES, WAREHOUSE
from .services import register_inventory_movement, transition_order


class ProductionWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ventas", password="test-pass-12345")
        for role in (SALES, KITCHEN, WAREHOUSE, DISPATCH):
            self.user.groups.add(Group.objects.get_or_create(name=role)[0])
        self.customer = Customer.objects.create(name="Camila", phone="+56912345678")
        self.flour = Ingredient.objects.create(
            name="Harina", unit="kg", stock=Decimal("3.000"), minimum_stock=Decimal("0.500"),
            unit_cost=Decimal("1500.00")
        )
        self.order = Order.objects.create(
            customer=self.customer,
            product="Torta de chocolate",
            design="Decoración floral",
            delivery_at=timezone.now() + timedelta(days=3),
            delivery_address="Av. Central 123",
            labor_cost=Decimal("5000.00"),
            quote_status=Order.QuoteStatus.APPROVED,
            created_by=self.user,
        )
        OrderIngredient.objects.create(order=self.order, ingredient=self.flour, quantity=Decimal("1.250"))

    def test_inventory_is_deducted_once_when_production_starts(self):
        transition_order(self.order.pk, Order.Status.PREPARING, self.user)
        self.flour.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.flour.stock, Decimal("1.750"))
        self.assertTrue(self.order.inventory_reserved)

    def test_insufficient_stock_does_not_change_order_or_inventory(self):
        self.flour.stock = Decimal("1.000")
        self.flour.save()
        with self.assertRaises(ValidationError):
            transition_order(self.order.pk, Order.Status.PREPARING, self.user)
        self.flour.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.flour.stock, Decimal("1.000"))
        self.assertEqual(self.order.status, Order.Status.RECEIVED)
        self.assertFalse(self.order.inventory_reserved)

    def test_production_requires_approved_quote(self):
        self.order.quote_status = Order.QuoteStatus.SENT
        self.order.save(update_fields=["quote_status"])
        with self.assertRaises(ValidationError):
            transition_order(self.order.pk, Order.Status.PREPARING, self.user)

    def test_production_requires_a_material_list(self):
        order_without_materials = Order.objects.create(
            customer=self.customer,
            product="Torta sin BOM",
            design="Diseño básico",
            delivery_at=timezone.now() + timedelta(days=4),
            delivery_address="Av. Principal 12",
            quote_status=Order.QuoteStatus.APPROVED,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            transition_order(order_without_materials.pk, Order.Status.PREPARING, self.user)
        order_without_materials.refresh_from_db()
        self.assertEqual(order_without_materials.status, Order.Status.RECEIVED)

    def test_quote_cannot_be_sent_without_material_lines(self):
        order_without_materials = Order.objects.create(
            customer=self.customer,
            product="Torta sin BOM",
            design="Diseño básico",
            delivery_at=timezone.now() + timedelta(days=4),
            delivery_address="Av. Principal 12",
            created_by=self.user,
        )
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.post(
            f"/api/pedidos/{order_without_materials.pk}/quote/",
            {"quote_status": Order.QuoteStatus.SENT},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        order_without_materials.refresh_from_db()
        self.assertEqual(order_without_materials.quote_status, Order.QuoteStatus.DRAFT)

    def test_cancellation_restores_reserved_inventory(self):
        transition_order(self.order.pk, Order.Status.PREPARING, self.user)
        transition_order(self.order.pk, Order.Status.CANCELLED, self.user)
        self.flour.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.flour.stock, Decimal("3.000"))
        self.assertFalse(self.order.inventory_reserved)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        movements = list(self.order.inventory_movements.order_by("direction"))
        self.assertEqual(len(movements), 2)
        self.assertEqual(movements[0].source, InventoryMovement.Source.CANCELLATION)
        self.assertEqual(movements[1].source, InventoryMovement.Source.PRODUCTION)

    def test_manual_inventory_movements_are_audited_and_cannot_overdraw(self):
        movement = register_inventory_movement(
            self.flour.pk, InventoryMovement.Direction.IN, Decimal("2.000"), "Compra", self.user
        )
        self.assertEqual(movement.stock_after, Decimal("5.000"))
        movement = register_inventory_movement(
            self.flour.pk, InventoryMovement.Direction.OUT, Decimal("1.000"), "Merma", self.user
        )
        self.assertEqual(movement.stock_after, Decimal("4.000"))
        with self.assertRaises(ValidationError):
            register_inventory_movement(
                self.flour.pk, InventoryMovement.Direction.OUT, Decimal("8.000"), "Ajuste", self.user
            )
        self.flour.refresh_from_db()
        self.assertEqual(self.flour.stock, Decimal("4.000"))
        self.assertEqual(self.flour.movements.count(), 2)

    def test_inventory_movement_web_form_records_an_entry(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/inventario/movimientos/nuevo/",
            {
                "ingredient": self.flour.pk,
                "direction": InventoryMovement.Direction.IN,
                "quantity": "1.500",
                "note": "Recepción de proveedor",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.flour.refresh_from_db()
        self.assertEqual(self.flour.stock, Decimal("4.500"))
        self.assertEqual(self.flour.movements.get().created_by, self.user)

    def test_stage_changes_must_be_sequential(self):
        with self.assertRaises(ValidationError):
            transition_order(self.order.pk, Order.Status.BAKED, self.user)
        transition_order(self.order.pk, Order.Status.PREPARING, self.user)
        transition_order(self.order.pk, Order.Status.BAKED, self.user)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.BAKED)

    def test_kanban_requires_login(self):
        response = self.client.get("/pedidos/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_workflow_pages_render(self):
        self.client.force_login(self.user)
        paths = [
            "/",
            "/pedidos/",
            "/pedidos/nuevo/",
            f"/pedidos/{self.order.pk}/",
            "/clientes/",
            "/insumos/",
            "/inventario/movimientos/",
            "/despachos/",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_order_form_creates_bom_lines_and_initial_history(self):
        self.client.force_login(self.user)
        delivery_at = (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            "/pedidos/nuevo/",
            {
                "customer": self.customer.pk,
                "product": "Torta de frutilla",
                "design": "Flores rosadas",
                "delivery_at": delivery_at,
                "delivery_address": "Calle 1",
                "notes": "",
                "labor_cost": "4000.00",
                "materials-TOTAL_FORMS": "3",
                "materials-INITIAL_FORMS": "0",
                "materials-MIN_NUM_FORMS": "0",
                "materials-MAX_NUM_FORMS": "1000",
                "materials-0-ingredient": self.flour.pk,
                "materials-0-quantity": "0.500",
                "materials-1-ingredient": "",
                "materials-1-quantity": "",
                "materials-2-ingredient": "",
                "materials-2-quantity": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        created_order = Order.objects.get(product="Torta de frutilla")
        self.assertEqual(created_order.materials.get().quantity, Decimal("0.500"))
        self.assertEqual(created_order.history.count(), 1)

    def test_customer_web_form_supports_create_edit_and_delete(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/clientes/nuevo/",
            {"name": "Nueva clienta", "phone": "+56955555555", "email": "cliente@example.com"},
        )
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name="Nueva clienta")
        response = self.client.post(
            f"/clientes/{customer.pk}/editar/",
            {"name": "Clienta actualizada", "phone": "+56944444444", "email": ""},
        )
        self.assertEqual(response.status_code, 302)
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Clienta actualizada")
        response = self.client.post(f"/clientes/{customer.pk}/eliminar/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=customer.pk).exists())

    def test_api_requires_authentication_and_returns_orders_after_login(self):
        response = self.client.get("/api/pedidos/")
        self.assertEqual(response.status_code, 403)
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.get("/api/pedidos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["number"], self.order.number)

    def test_delivered_dispatch_requires_a_proof(self):
        self.order.status = Order.Status.READY
        self.order.save(update_fields=["status"])
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.post(
            "/api/despachos/",
            {
                "order": self.order.pk,
                "driver": "Reparto",
                "route_order": 1,
                "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat(),
                "status": "DELIVERED",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("proof_text", response.data)

    def test_dispatch_web_form_accepts_signature_proof_for_ready_order(self):
        self.order.status = Order.Status.READY
        self.order.save(update_fields=["status"])
        self.client.force_login(self.user)
        page = self.client.get("/despachos/nuevo/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="signature-pad"')
        scheduled_at = (timezone.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            "/despachos/nuevo/",
            {
                "order": self.order.pk,
                "driver": "Reparto",
                "route_order": 1,
                "scheduled_at": scheduled_at,
                "status": Dispatch.Status.DELIVERED,
                "proof_text": "Firma de recepción: Cliente",
            },
        )
        self.assertEqual(response.status_code, 302)
        dispatch = Dispatch.objects.get(order=self.order)
        self.assertIsNotNone(dispatch.delivered_at)
        self.assertEqual(dispatch.proof_text, "Firma de recepción: Cliente")

    def test_api_cannot_approve_quote_via_generic_update(self):
        self.order.quote_status = Order.QuoteStatus.DRAFT
        self.order.save(update_fields=["quote_status"])
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.patch(
            f"/api/pedidos/{self.order.pk}/",
            {"quote_status": Order.QuoteStatus.APPROVED},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quote_status"], Order.QuoteStatus.DRAFT)

    def test_roles_restrict_web_and_api_mutations(self):
        restricted_user = get_user_model().objects.create_user(username="solo-lectura", password="test-pass-12345")
        self.client.force_login(restricted_user)
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/clientes/nuevo/")
        self.assertEqual(response.status_code, 403)
        response = self.client.get("/clientes/")
        self.assertEqual(response.status_code, 200)
        api_client = APIClient()
        api_client.force_authenticate(restricted_user)
        response = api_client.post(
            "/api/clientes/",
            {"name": "No autorizado", "phone": "123"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_sales_role_cannot_advance_production(self):
        sales_user = get_user_model().objects.create_user(username="solo-ventas", password="test-pass-12345")
        sales_user.groups.add(Group.objects.get(name=SALES))
        self.client.force_login(sales_user)
        response = self.client.post(
            f"/pedidos/{self.order.pk}/estado/",
            {"status": Order.Status.PREPARING},
        )
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.RECEIVED)

    def test_api_inventory_entry_records_stock_movement(self):
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.post(
            "/api/movimientos-inventario/",
            {
                "ingredient": self.flour.pk,
                "direction": InventoryMovement.Direction.IN,
                "quantity": "1.000",
                "note": "Compra",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.flour.refresh_from_db()
        self.assertEqual(self.flour.stock, Decimal("4.000"))
        self.assertEqual(self.flour.movements.count(), 1)

    def test_api_customer_and_ingredient_crud_preserves_inventory_control(self):
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        customer_response = api_client.post(
            "/api/clientes/",
            {"name": "API clienta", "phone": "+56977777777", "email": ""},
            format="json",
        )
        self.assertEqual(customer_response.status_code, 201)
        customer_id = customer_response.data["id"]
        response = api_client.patch(
            f"/api/clientes/{customer_id}/", {"name": "API actualizada"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "API actualizada")
        self.assertEqual(api_client.delete(f"/api/clientes/{customer_id}/").status_code, 204)

        ingredient_response = api_client.post(
            "/api/insumos/",
            {"name": "Azúcar", "unit": "kg", "stock": "50.000", "minimum_stock": "1.000", "unit_cost": "900"},
            format="json",
        )
        self.assertEqual(ingredient_response.status_code, 201)
        ingredient_id = ingredient_response.data["id"]
        self.assertEqual(ingredient_response.data["stock"], "0.000")
        response = api_client.patch(
            f"/api/insumos/{ingredient_id}/",
            {"stock": "100.000", "unit_cost": "950"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stock"], "0.000")
        self.assertEqual(response.data["unit_cost"], "950.00")
        self.assertEqual(api_client.delete(f"/api/insumos/{ingredient_id}/").status_code, 204)

    def test_order_api_create_update_delete_and_dispatch_api_lifecycle(self):
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.post(
            "/api/pedidos/",
            {
                "customer": self.customer.pk,
                "product": "Torta API",
                "design": "Diseño API",
                "delivery_at": (timezone.now() + timedelta(days=6)).isoformat(),
                "delivery_address": "Calle API 1",
                "labor_cost": "2500.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        order_id = response.data["id"]
        response = api_client.patch(
            f"/api/pedidos/{order_id}/", {"product": "Torta API editada"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product"], "Torta API editada")
        self.assertEqual(api_client.delete(f"/api/pedidos/{order_id}/").status_code, 204)

        self.order.status = Order.Status.READY
        self.order.save(update_fields=["status"])
        response = api_client.post(
            "/api/despachos/",
            {
                "order": self.order.pk,
                "driver": "Reparto API",
                "route_order": 1,
                "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat(),
                "status": Dispatch.Status.PLANNED,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        dispatch_id = response.data["id"]
        response = api_client.patch(
            f"/api/despachos/{dispatch_id}/",
            {"status": Dispatch.Status.IN_ROUTE},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        response = api_client.patch(
            f"/api/despachos/{dispatch_id}/",
            {"status": Dispatch.Status.DELIVERED, "proof_text": "Firma API"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["delivered_at"])
        self.assertEqual(api_client.delete(f"/api/despachos/{dispatch_id}/").status_code, 400)

    def test_api_prevents_deleting_referenced_customer_or_ingredient(self):
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        customer_response = api_client.delete(f"/api/clientes/{self.customer.pk}/")
        ingredient_response = api_client.delete(f"/api/insumos/{self.flour.pk}/")
        self.assertEqual(customer_response.status_code, 400)
        self.assertEqual(ingredient_response.status_code, 400)

    def test_users_without_warehouse_role_cannot_change_stock(self):
        restricted_user = get_user_model().objects.create_user(username="solo-ventas", password="test-pass-12345")
        restricted_user.groups.add(Group.objects.get(name=SALES))
        api_client = APIClient()
        api_client.force_authenticate(restricted_user)
        response = api_client.post(
            "/api/movimientos-inventario/",
            {
                "ingredient": self.flour.pk,
                "direction": InventoryMovement.Direction.IN,
                "quantity": "1.000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_bom_cannot_be_changed_after_quote_is_approved(self):
        self.order.quote_status = Order.QuoteStatus.APPROVED
        self.order.save(update_fields=["quote_status"])
        api_client = APIClient()
        api_client.force_authenticate(self.user)
        response = api_client.patch(
            f"/api/materiales-pedido/{self.order.materials.get().pk}/",
            {"quantity": "2.000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_required_domain_models_are_registered_in_admin(self):
        for model in (Customer, Ingredient, InventoryMovement, Order, OrderIngredient, OrderStatusHistory, Dispatch):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)
