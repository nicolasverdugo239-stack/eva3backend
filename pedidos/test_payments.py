from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Customer, Order, Payment
from .payment_services import register_payment
from .roles import SALES


class PaymentTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ventas_pagos",
            password="test-pass-12345",
        )
        group, _ = Group.objects.get_or_create(name=SALES)
        self.user.groups.add(group)

        self.customer = Customer.objects.create(
            name="Cliente de prueba",
            phone="+56912345678",
        )

        self.order = Order.objects.create(
            customer=self.customer,
            product="Torta de prueba",
            design="Decoración sencilla",
            delivery_at=timezone.now() + timedelta(days=3),
            delivery_address="Dirección de prueba",
            labor_cost=Decimal("5000.00"),
            sale_price=Decimal("50000.00"),
            created_by=self.user,
        )

    def test_valid_payment(self):
        register_payment(
            order_id=self.order.pk,
            amount=Decimal("20000.00"),
            method=Payment.Method.TRANSFER,
            user=self.user,
        )

        self.assertEqual(
            self.order.total_paid,
            Decimal("20000.00"),
        )
        self.assertEqual(
            self.order.balance_due,
            Decimal("30000.00"),
        )

    def test_payment_cannot_exceed_balance(self):
        with self.assertRaises(ValidationError):
            register_payment(
                order_id=self.order.pk,
                amount=Decimal("60000.00"),
                method=Payment.Method.CASH,
                user=self.user,
            )

        self.assertEqual(Payment.objects.count(), 0)

    def test_cancelled_order_rejects_payment(self):
        self.order.status = Order.Status.CANCELLED
        self.order.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            register_payment(
                order_id=self.order.pk,
                amount=Decimal("10000.00"),
                method=Payment.Method.CARD,
                user=self.user,
            )

        self.assertEqual(Payment.objects.count(), 0)
