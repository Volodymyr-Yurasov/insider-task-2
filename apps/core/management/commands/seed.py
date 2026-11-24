"""Populate the database with demo data. Safe to run any number of times.

Every record is matched on its natural key and only created when missing; existing rows
(e.g. a changed admin password or an edited location) are never overwritten.
"""

import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import Q

from apps.locations.cache import invalidate_location_list_cache
from apps.locations.models import Category, Location
from apps.reviews.models import Review, ReviewVote

# Arbitrary constant identifying the seed lock across processes / containers.
SEED_ADVISORY_LOCK_ID = 727_001

ADMIN_USERNAME = "admin"

USERS = ["olena", "taras", "iryna", "dmytro", "sofia"]

CATEGORIES = [
    ("Parks", "parks"),
    ("Museums", "museums"),
    ("Historic sites", "historic-sites"),
    ("Viewpoints", "viewpoints"),
]

# (name, category slug, author, address, lat, lng, description)
LOCATIONS = [
    (
        "Hydropark",
        "parks",
        "olena",
        "Hidropark, Kyiv",
        "50.445000",
        "30.577000",
        "Island park on the Dnipro with beaches and sports grounds.",
    ),
    (
        "Mariinskyi Park",
        "parks",
        "taras",
        "Mykhaila Hrushevskoho St, Kyiv",
        "50.447500",
        "30.537000",
        "Shady 19th-century park next to the Mariinskyi Palace.",
    ),
    (
        "National Art Museum of Ukraine",
        "museums",
        "iryna",
        "6 Mykhaila Hrushevskoho St, Kyiv",
        "50.449700",
        "30.530000",
        "Ukrainian art from medieval icons to the 20th century.",
    ),
    (
        "National Museum of the History of Ukraine in WWII",
        "museums",
        "dmytro",
        "24 Lavrska St, Kyiv",
        "50.426500",
        "30.563000",
        "Museum complex beneath the Motherland Monument.",
    ),
    (
        "Golden Gate",
        "historic-sites",
        "sofia",
        "40A Volodymyrska St, Kyiv",
        "50.448900",
        "30.513300",
        "Reconstructed main gate of 11th-century Kyiv.",
    ),
    (
        "Kyiv Pechersk Lavra",
        "historic-sites",
        "olena",
        "15 Lavrska St, Kyiv",
        "50.434400",
        "30.557400",
        "Historic monastery complex with caves and bell tower.",
    ),
    (
        "Volodymyrska Hill",
        "viewpoints",
        "taras",
        "Volodymyrskyi Descent, Kyiv",
        "50.455600",
        "30.525100",
        "Park terraces with one of the best views over the Dnipro.",
    ),
    (
        "Andriivskyi Descent",
        "historic-sites",
        "iryna",
        "Andriivskyi Descent, Kyiv",
        "50.459000",
        "30.517600",
        "Cobbled street of galleries and souvenir stalls.",
    ),
]

# (location name, reviewer, rating, comment). Reviewers never review their own location.
REVIEWS = [
    ("Hydropark", "taras", 5, "Perfect for a summer day by the river."),
    ("Hydropark", "iryna", 4, "Great beaches, a bit crowded on weekends."),
    ("Hydropark", "dmytro", 4, "Lots of space for running and cycling."),
    ("Hydropark", "sofia", 5, "My favourite place to swim in the city."),
    ("Mariinskyi Park", "olena", 4, "Calm and green, right in the centre."),
    ("Mariinskyi Park", "sofia", 3, "Nice, but some paths need repair."),
    ("National Art Museum of Ukraine", "olena", 5, "Wonderful icon collection."),
    ("National Art Museum of Ukraine", "taras", 4, "Plan at least two hours."),
    ("National Museum of the History of Ukraine in WWII", "sofia", 5, "Powerful and moving."),
    ("National Museum of the History of Ukraine in WWII", "iryna", 5, "A must-see."),
    ("National Museum of the History of Ukraine in WWII", "olena", 4, "Very informative."),
    ("Golden Gate", "dmytro", 3, "Interesting history, small inside."),
    ("Golden Gate", "taras", 4, "Worth a quick stop on a walk."),
    ("Kyiv Pechersk Lavra", "taras", 5, "Breathtaking architecture."),
    ("Kyiv Pechersk Lavra", "iryna", 5, "The caves are unforgettable."),
    ("Kyiv Pechersk Lavra", "dmytro", 4, "Bring comfortable shoes."),
    ("Kyiv Pechersk Lavra", "sofia", 5, "Spent the whole day here."),
    ("Volodymyrska Hill", "olena", 5, "Best sunset view in Kyiv."),
    ("Volodymyrska Hill", "dmytro", 4, "Beautiful in any season."),
    ("Andriivskyi Descent", "sofia", 4, "Charming street with great vibes."),
    ("Andriivskyi Descent", "olena", 2, "Too touristy for me."),
]

# (location name, review author, voter, value). Voters never vote on their own review.
VOTES = [
    ("Hydropark", "taras", "olena", 1),
    ("Hydropark", "taras", "iryna", 1),
    ("Hydropark", "iryna", "dmytro", 1),
    ("Hydropark", "sofia", "taras", -1),
    ("Kyiv Pechersk Lavra", "iryna", "olena", 1),
    ("Kyiv Pechersk Lavra", "iryna", "sofia", 1),
    ("Kyiv Pechersk Lavra", "dmytro", "taras", 1),
    ("Golden Gate", "dmytro", "sofia", -1),
    ("Golden Gate", "dmytro", "olena", -1),
    ("Andriivskyi Descent", "olena", "iryna", -1),
    ("Andriivskyi Descent", "olena", "sofia", 1),
    ("National Museum of the History of Ukraine in WWII", "sofia", "dmytro", 1),
]


class Command(BaseCommand):
    help = "Seed demo users, admin, categories, locations, reviews and votes (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-password", default=os.environ.get("SEED_ADMIN_PASSWORD", "Admin-pass-123")
        )
        parser.add_argument(
            "--user-password", default=os.environ.get("SEED_USER_PASSWORD", "Demo-pass-123")
        )

    def handle(self, *args, admin_password, user_password, **options):
        with transaction.atomic():
            self._lock()
            created = {
                "admin": self._seed_admin(admin_password),
                "users": 0,
                "categories": 0,
                "locations": 0,
            }
            users = self._seed_users(user_password, created)
            categories = self._seed_categories(created)
            locations = self._seed_locations(users, categories, created)
            created["reviews"] = self._seed_reviews(users, locations)
            created["votes"] = self._seed_votes(users, locations)
            invalidate_location_list_cache()

        summary = ", ".join(f"{name}: +{int(count)}" for name, count in created.items())
        self.stdout.write(self.style.SUCCESS(f"Seed complete ({summary})"))

    def _lock(self):
        """Serialize concurrent runs (e.g. several containers starting at once).

        Released automatically when the transaction ends.
        """
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [SEED_ADVISORY_LOCK_ID])

    @staticmethod
    def _find_user(username: str, email: str):
        # Match on either unique key, so a pre-existing account never causes an IntegrityError.
        return (
            get_user_model()
            .objects.filter(Q(username=username) | Q(email__iexact=email))
            .order_by("pk")
            .first()
        )

    def _seed_admin(self, password) -> bool:
        email = "admin@example.com"
        if self._find_user(ADMIN_USERNAME, email) is not None:
            return False
        get_user_model().objects.create_superuser(
            username=ADMIN_USERNAME, email=email, password=password
        )
        return True

    def _seed_users(self, password, created) -> dict:
        users = {}
        for username in USERS:
            email = f"{username}@example.com"
            user = self._find_user(username, email)
            if user is None:
                user = get_user_model().objects.create_user(
                    username=username, email=email, password=password
                )
                created["users"] += 1
            users[username] = user
        return users

    def _seed_categories(self, created) -> dict:
        categories = {}
        for name, slug in CATEGORIES:
            category = (
                Category.objects.filter(Q(slug=slug) | Q(name__iexact=name)).order_by("pk").first()
            )
            if category is None:
                category = Category.objects.create(name=name, slug=slug)
                created["categories"] += 1
            categories[slug] = category
        return categories

    def _seed_locations(self, users, categories, created) -> dict:
        locations = {}
        for name, slug, author, address, lat, lng, description in LOCATIONS:
            # all_objects: a soft-deleted demo location counts as existing and is not recreated.
            location = (
                Location.all_objects.filter(name=name, author=users[author]).order_by("pk").first()
            )
            if location is None:
                location = Location.objects.create(
                    name=name,
                    author=users[author],
                    category=categories[slug],
                    address=address,
                    latitude=Decimal(lat),
                    longitude=Decimal(lng),
                    description=description,
                )
                created["locations"] += 1
            locations[name] = location
        return locations

    def _seed_reviews(self, users, locations) -> int:
        """bulk_create skips post_save, so seeding sends no notification emails;
        ignore_conflicts relies on the one-review-per-user-per-location constraint."""
        before = Review.objects.count()
        Review.objects.bulk_create(
            [
                Review(
                    location=locations[location],
                    author=users[reviewer],
                    rating=rating,
                    comment=comment,
                )
                for location, reviewer, rating, comment in REVIEWS
            ],
            ignore_conflicts=True,
        )
        return Review.objects.count() - before

    def _seed_votes(self, users, locations) -> int:
        reviews = {
            (review.location_id, review.author_id): review
            for review in Review.objects.filter(location__in=locations.values())
        }
        votes = []
        for location, review_author, voter, value in VOTES:
            review = reviews.get((locations[location].pk, users[review_author].pk))
            if review is not None:
                votes.append(ReviewVote(review=review, user=users[voter], value=value))
        before = ReviewVote.objects.count()
        ReviewVote.objects.bulk_create(votes, ignore_conflicts=True)
        return ReviewVote.objects.count() - before
