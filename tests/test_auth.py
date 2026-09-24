"""JWT authentication, roles, proposer != approver, and the development token endpoint."""

import time
from pathlib import Path

import jwt
import pytest
from auth_helpers import APPROVE, REJECT, bearer
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from aegisops.api.app import create_app
from aegisops.api.auth import TokenVerifier
from aegisops.core.config import DEFAULT_SECRET_KEY, Settings
from backend.db.models import Base


def _app(**settings: object):  # type: ignore[no-untyped-def]
    return create_app(Settings(**{"environment": "test", "database_url": "sqlite://", **settings}))


def _post_decision(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post("/api/v1/decisions", json={"seed": 1}, headers=headers)
    assert response.status_code == 200, response.text
    return int(response.json()["decision_id"])


def _approvable_decision(client: TestClient, proposer: dict[str, str]) -> int:
    for seed in range(50):
        body = client.post("/api/v1/decisions", json={"seed": seed}, headers=proposer).json()
        if body["status"] == "requires_human_approval":
            return int(body["decision_id"])
    raise AssertionError("no approvable seed found")


@pytest.mark.parametrize(
    ("role", "expected"), [("viewer", 403), ("operator", 200), ("approver", 200), ("admin", 200)]
)
def test_creating_a_decision_requires_operator_or_higher(role: str, expected: int) -> None:
    response = TestClient(_app()).post(
        "/api/v1/decisions", json={"seed": 1}, headers=bearer("u", role)
    )

    assert response.status_code == expected


def _encode(claims: dict[str, object], key: str = DEFAULT_SECRET_KEY, alg: str = "HS256") -> str:
    return jwt.encode(claims, key, algorithm=alg)


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        _encode({"sub": "u", "role": "operator", "exp": int(time.time()) - 3600}),
        _encode({"sub": "u", "role": "operator", "exp": int(time.time()) + 60}, key="k" * 40),
        _encode({"sub": "u", "role": "superuser", "exp": int(time.time()) + 60}),
        _encode({"role": "operator", "exp": int(time.time()) + 60}),
        _encode({"sub": "u", "role": "operator"}),
        jwt.encode(
            {"sub": "u", "role": "admin", "exp": int(time.time()) + 60}, None, algorithm="none"
        ),
    ],
    ids=["garbage", "expired", "wrong-key", "unknown-role", "no-sub", "no-exp", "alg-none"],
)
def test_invalid_tokens_are_rejected(token: str) -> None:
    response = TestClient(_app()).post(
        "/api/v1/decisions", json={"seed": 1}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_missing_token_is_rejected_even_in_the_test_environment() -> None:
    assert TestClient(_app()).post("/api/v1/decisions", json={"seed": 1}).status_code == 401


def test_role_list_claim_resolves_to_the_most_privileged_role() -> None:
    token = _encode({"sub": "u", "role": ["viewer", "approver"], "exp": int(time.time()) + 60})

    principal = TokenVerifier(Settings(environment="test")).verify(token)

    assert principal.role.value == "approver"


def test_proposer_cannot_approve_their_own_decision() -> None:
    client = TestClient(_app())
    carol = bearer("carol", "approver")
    decision_id = _approvable_decision(client, carol)

    response = client.post(
        f"/api/v1/decisions/{decision_id}/disposition",
        json={**APPROVE, "reason": "Looks fine to me."},
        headers=carol,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "proposer cannot approve"


def test_a_different_approver_can_approve() -> None:
    client = TestClient(_app())
    decision_id = _approvable_decision(client, bearer("carol", "approver"))

    response = client.post(
        f"/api/v1/decisions/{decision_id}/disposition",
        json={**APPROVE, "reason": "Second pair of eyes."},
        headers=bearer("dave", "approver"),
    )

    assert response.status_code == 200
    record = client.get(f"/api/v1/decisions/{decision_id}", headers=bearer()).json()
    assert record["proposer_sub"] == "carol"
    assert record["approvals"][0]["actor"] == "dave"


def test_operators_can_reject_but_not_approve() -> None:
    client = TestClient(_app())
    decision_id = _approvable_decision(client, bearer("alice", "operator"))
    url = f"/api/v1/decisions/{decision_id}/disposition"

    approve = client.post(url, json={**APPROVE, "reason": "x"}, headers=bearer("op2"))
    reject = client.post(url, json={**REJECT, "reason": "x"}, headers=bearer("alice"))

    assert approve.status_code == 403
    assert reject.status_code == 200


def test_dev_token_endpoint_only_exists_in_development(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'dev.db'}"
    Base.metadata.create_all(create_engine(url))
    development = TestClient(_app(environment="development", database_url=url))
    token = development.post(
        "/api/v1/dev/token", json={"sub": "alice", "role": "operator"}
    ).json()["access_token"]

    created = development.post(
        "/api/v1/decisions", json={"seed": 1}, headers={"Authorization": f"Bearer {token}"}
    )

    assert created.status_code == 200
    for environment, secret in (("test", DEFAULT_SECRET_KEY), ("production", "p" * 48)):
        app = _app(environment=environment, secret_key=secret)
        response = TestClient(app).post("/api/v1/dev/token", json={"sub": "a", "role": "admin"})
        assert response.status_code == 404


def test_default_environment_is_production() -> None:
    assert Settings(_env_file=None).environment == "production"  # type: ignore[call-arg]


def test_refuses_to_start_outside_development_with_the_published_key() -> None:
    with pytest.raises(RuntimeError, match="AEGISOPS_SECRET_KEY"):
        _app(environment="production")
    assert _app(environment="production", secret_key="p" * 48) is not None


class _StaticJwks(jwt.PyJWKClient):
    def __init__(self, jwk: dict[str, object]) -> None:
        super().__init__("https://idp.example.test/jwks")
        self._jwk = jwk

    def fetch_data(self) -> dict[str, object]:
        return {"keys": [self._jwk]}


def test_rs256_tokens_from_an_oidc_jwks_are_accepted_and_hs256_is_not() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    settings = Settings(
        environment="test",
        database_url="sqlite://",
        jwt_algorithm="RS256",
        jwt_issuer="https://idp.example.test",
        jwt_audience="aegisops",
    )
    app = create_app(settings, token_verifier=TokenVerifier(settings, _StaticJwks(jwk)))
    claims = {
        "sub": "oidc|123",
        "role": "operator",
        "iss": "https://idp.example.test",
        "aud": "aegisops",
        "exp": int(time.time()) + 60,
    }
    rs256 = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "k1"})
    forged = jwt.encode(claims, DEFAULT_SECRET_KEY, algorithm="HS256", headers={"kid": "k1"})
    client = TestClient(app)

    accepted = client.post(
        "/api/v1/decisions", json={"seed": 1}, headers={"Authorization": f"Bearer {rs256}"}
    )
    rejected = client.post(
        "/api/v1/decisions", json={"seed": 1}, headers={"Authorization": f"Bearer {forged}"}
    )

    assert accepted.status_code == 200
    assert accepted.json()["proposer_sub"] == "oidc|123"
    assert rejected.status_code == 401
