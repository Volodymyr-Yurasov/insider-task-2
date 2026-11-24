import csv
import io
import json

import pytest
from django.urls import reverse

from apps.reviews.tests.factories import ReviewFactory

from .factories import CategoryFactory, LocationFactory

pytestmark = pytest.mark.django_db

EXPORT_URL = reverse("locations:location-export")
EXPECTED_COLUMNS = [
    "id",
    "name",
    "description",
    "category",
    "address",
    "latitude",
    "longitude",
    "author",
    "rating",
    "reviews_count",
    "views_7d",
    "popularity",
    "created_at",
    "updated_at",
]


@pytest.fixture
def locations():
    parks = CategoryFactory(name="Parks", slug="parks")
    park = LocationFactory(name="Hydropark", category=parks)
    ReviewFactory(location=park, rating=4)
    museum = LocationFactory(name="Музей")
    deleted = LocationFactory(name="Gone")
    deleted.delete()
    return park, museum


def test_csv_export_is_the_default(api_client, locations):
    response = api_client.get(EXPORT_URL)  # no file_format: CSV

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"].startswith('attachment; filename="locations-')
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert list(rows[0]) == EXPECTED_COLUMNS
    assert {r["name"] for r in rows} == {"Hydropark", "Музей"}
    park = next(r for r in rows if r["name"] == "Hydropark")
    assert park["category"] == "Parks"
    assert float(park["rating"]) == 4.0


def test_json_export(api_client, locations):
    response = api_client.get(EXPORT_URL, {"file_format": "json"})

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    data = json.loads(response.content)
    assert len(data) == 2
    assert list(data[0]) == EXPECTED_COLUMNS
    museum = next(r for r in data if r["name"] == "Музей")
    assert museum["rating"] is None
    assert museum["reviews_count"] == 0


def test_export_respects_filters(api_client, locations):
    park, _ = locations

    response = api_client.get(EXPORT_URL, {"file_format": "json", "category_slug": "parks"})

    assert [r["id"] for r in json.loads(response.content)] == [park.id]


def test_unknown_format_is_rejected(api_client):
    response = api_client.get(EXPORT_URL, {"file_format": "xml"})

    assert response.status_code == 400
    assert "file_format" in response.data
