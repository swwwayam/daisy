"""Ownership must fail closed for unknown resources and different users."""
import unittest

from resource_access import ResourceOwners


class ResourceOwnerTests(unittest.TestCase):
    def test_owner_can_access_but_another_user_cannot(self):
        owners = ResourceOwners()
        owners.register("dataset-a", "user-a")
        self.assertTrue(owners.permits("dataset-a", "user-a"))
        self.assertFalse(owners.permits("dataset-a", "user-b"))
        self.assertFalse(owners.permits("missing", "user-a"))
        self.assertFalse(owners.permits("dataset-a", ""))

    def test_existing_resource_cannot_be_taken_over(self):
        owners = ResourceOwners()
        owners.register("dataset-a", "user-a")
        owners.register("dataset-a", "user-a")
        with self.assertRaises(ValueError):
            owners.register("dataset-a", "user-b")
        self.assertTrue(owners.permits("dataset-a", "user-a"))

    def test_registration_requires_an_owner(self):
        with self.assertRaises(ValueError):
            ResourceOwners().register("dataset-a", "")

