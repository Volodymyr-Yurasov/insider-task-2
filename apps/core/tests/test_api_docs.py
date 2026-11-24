import pytest

pytestmark = pytest.mark.django_db


def test_swagger_page_syncs_csrf_header_with_cookie(api_client):
    """Swagger must read the live csrftoken cookie, because login rotates the token."""
    response = api_client.get("/api/docs/")

    assert response.status_code == 200
    page = response.content.decode()
    assert "window.fetch = (input, init) =>" in page
    assert "csrftoken=" in page
    # The wrapper must be defined before Swagger UI's bundle is loaded.
    assert page.index("window.fetch =") < page.index("swagger-ui-bundle")
