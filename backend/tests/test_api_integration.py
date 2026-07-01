"""API 集成测试: 端点正确性、错误处理、响应格式"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """同步 TestClient — 使用项目真实 DB（需要 seed_data 预先运行）"""
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["status"] == "ok"


class TestDistricts:
    def test_list_districts(self, client):
        resp = client.get("/api/v1/districts")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["data"], list)

    def test_district_not_found(self, client):
        resp = client.get("/api/v1/districts/99999/stats")
        assert resp.status_code == 200
        assert resp.json()["code"] == 404


class TestListings:
    def test_empty_ok(self, client):
        """空数据库返回合法响应"""
        resp = client.get("/api/v1/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data["data"]
        assert "total" in data["data"]

    def test_not_found(self, client):
        resp = client.get("/api/v1/listings/99999")
        assert resp.status_code == 200
        assert resp.json()["code"] == 404

    def test_summary(self, client):
        resp = client.get("/api/v1/listings/stats/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_listings"] >= 0


class TestCrawl:
    def test_batches_empty(self, client):
        resp = client.get("/api/v1/crawl/batches")
        assert resp.status_code == 200

    def test_status_not_found(self, client):
        resp = client.get("/api/v1/crawl/status/99999")
        assert resp.json()["code"] == 404

    def test_stop_no_active(self, client):
        resp = client.post("/api/v1/crawl/stop/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["stopped"] is False


class TestErrorEnvelope:
    def test_missing_listing(self, client):
        resp = client.get("/api/v1/listings/99999")
        data = resp.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data
        assert isinstance(data["code"], int)


class TestPagination:
    def test_pagination_fields(self, client):
        resp = client.get("/api/v1/listings?page=1&page_size=5")
        data = resp.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5

    def test_page_zero_rejected(self, client):
        assert client.get("/api/v1/listings?page=0").status_code == 422

    def test_page_size_too_large(self, client):
        assert client.get("/api/v1/listings?page_size=500").status_code == 422


class TestOpenAPI:
    def test_docs(self, client):
        assert client.get("/docs").status_code == 200

    def test_openapi_schema(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = list(resp.json()["paths"].keys())
        assert any("listings" in p for p in paths)
        assert any("crawl" in p for p in paths)
        assert any("analytics" in p for p in paths)
