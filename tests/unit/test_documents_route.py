def test_list_documents_with_valid_metadata_filter(client):
    response = client.get(
        "/v1/documents",
        params={"specialty": "cardiology"},
    )

    assert response.status_code == 200
    assert response.json()["filters"] == {"specialty": "cardiology"}


def test_list_documents_rejects_invalid_filter_name(client):
    response = client.get(
        "/v1/documents",
        params={"invalid-key": "value"},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["detail"] == "Invalid filter name: invalid-key"
