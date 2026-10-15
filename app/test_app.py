import pytest
import app as app_module


class FakePipe:
    def __init__(self, cache):
        self.cache = cache
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))

    def expire(self, key, window):
        pass

    def execute(self):
        for op, key in self.ops:
            if op == "incr":
                self.cache.store[key] = str(int(self.cache.store.get(key, 0)) + 1)


class FakeCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value

    def pipeline(self):
        return FakePipe(self)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "cache", FakeCache())
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_base62_roundtrip():
    for n in [1, 61, 62, 12345, 999999999]:
        assert app_module.base62_decode(app_module.base62_encode(n)) == n


def test_base62_zero():
    assert app_module.base62_encode(0) == "0"


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "healthy"}


def test_shorten_missing_url_returns_400(client):
    res = client.post("/shorten", json={})
    assert res.status_code == 400


def test_redirect_cache_hit(client):
    app_module.cache.set("abc", "https://example.com")
    res = client.get("/abc")
    assert res.status_code == 302
    assert res.headers["Location"] == "https://example.com"


def test_rate_limit_blocks_after_10_requests(client):
    for _ in range(10):
        client.post("/shorten", json={})
    res = client.post("/shorten", json={})
    assert res.status_code == 429