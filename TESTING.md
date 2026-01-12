# Project Testing & Mocking Conventions (Cursor Guide — January 2026 v2)

> **Purpose:** Testing conventions for AI-assisted code generation and human developers. Follow these rules when writing, reviewing, or generating tests.

> **Philosophy:** Pragmatic, not dogmatic. These are strong defaults with documented escape hatches.

---

## Test File Location

```
tests/unit/<app_label>/test_<module>.py
tests/integration/<app_label>/test_<module>.py
```

**Examples:**
- `tests/unit/orders/test_services.py`
- `tests/integration/users/test_api_views.py`

---

## Test Naming Convention

```
test_<function_or_method>_<condition_or_scenario>_<expected_outcome>
```

**Examples:**
- `test_create_order_when_stock_available_returns_success`
- `test_payment_webhook_raises_400_on_invalid_signature`
- `test_get_user_with_invalid_id_raises_not_found`

---

## Mocking Style

- **Primary:** `@patch` decorator from `unittest.mock`
- **Prefer** `autospec=True` by default
- **Disable autospec** for highly dynamic clients (boto3, some OAuth libs, protocol classes)
  - Symptom: `AttributeError` on mock because real object adds attributes at runtime
- Use `with patch(...) as mock_xxx:` for short scopes or multiple behaviors
- Use `PropertyMock` for `@property` / `cached_property`
- Patch at **highest stable boundary** (SDK client → gateway/service → rarely ORM)

### Alternative: pytest-mock

Use `mocker` fixture from `pytest-mock` for function-scoped patches:
- Cleaner syntax, auto-cleanup
- Access via `mocker.patch(...)`

---

## side_effect Guidance (Be Explicit)

| Pattern | When to Use | Example |
|---------|-------------|---------|
| `return_value=x` | Same response every time (default choice) | `mock.return_value = {"id": 1}` |
| `side_effect=[v1, v2, v3]` | Sequential calls return different values | `mock.side_effect = [User(), None, ValueError()]` |
| `side_effect=callable` | Conditional logic based on input args | `mock.side_effect = lambda x: x * 2` |
| `side_effect=ExceptionClass` | Always raise an exception | `mock.side_effect = ConnectionError("timeout")` |

---

## HTTP Mocking

| Library | Mock Tool |
|---------|-----------|
| `requests` | `responses` |
| `httpx` | `respx` (async-native) |

These are **complements**, not alternatives. Use both if your codebase uses both HTTP libs.

---

## Datetime Mocking

**Pick ONE per project** (not both):

| Library | Notes |
|---------|-------|
| `freezegun` | More mature, wider adoption |
| `time-machine` | Faster for large test suites |

---

## Test Data Creation

**Pick ONE per project:**

| Library | Best For |
|---------|----------|
| `factory_boy` | Complex relations, sequences, traits, lazy attributes |
| `model_bakery` | Simpler API, faster setup, "just give me an object" |

Both are better than raw `Model.objects.create()`.

---

## Database Test Markers

| Marker / Class | When to Use | Speed |
|----------------|-------------|-------|
| `@pytest.mark.django_db` | Most tests (uses transaction rollback) | Fast |
| `@pytest.mark.django_db(transaction=True)` | Testing transaction behavior, signals on commit | Slower |
| `TransactionTestCase` | Multi-database, testing DB constraints | Slowest |

**Default:** Use `@pytest.mark.django_db` unless you specifically need transaction semantics.

---

## Async Guidance (Django 4.x+ / 5.x)

**Preferred approach:** Use `AsyncClient` for most async view testing (full request lifecycle).

```python
@pytest.mark.asyncio
@pytest.mark.django_db
async def test_async_view():
    client = AsyncClient()
    response = await client.get("/api/endpoint/")
    assert response.status_code == 200
```

**Alternative:** Use `AsyncRequestFactory` only when you need low-level ASGI request crafting.

**Mocking async code:**
- Use `AsyncMock` from `unittest.mock`
- Or `mocker.patch(..., new_callable=AsyncMock)`
- Wrap sync ORM calls with `sync_to_async` when inside async tests

---

## Assertion Style

- Plain `assert` for value checks (pytest style)
- `pytest.raises(...)` for exceptions
- `mock.assert_called_once_with(...)` for verifying mock interactions
- `assert_has_calls([call(...)])` for multiple calls
- Prefer explicit arguments; use `ANY` only when argument is truly unpredictable

---

## Coverage & Parallelization

**Run tests with coverage:**

```bash
pytest --cov= --cov-branch --cov-report=term-missing
```

**Run tests in parallel (faster CI):**

```bash
pytest -n auto  # requires pytest-xdist
```

**Note:** Parallel tests require proper database isolation. Use `@pytest.mark.django_db` (not shared fixtures with state).

---

## Property-Based Testing (Optional but Powerful)

For validation-heavy code, consider `hypothesis`:

```python
from hypothesis import given, strategies as st

@given(st.emails())
def test_email_validation_accepts_valid_emails(email):
    assert is_valid_email(email) is True

@given(st.text())
def test_email_validation_rejects_garbage(text):
    # Most random strings are not valid emails
    # hypothesis will find edge cases you didn't think of
    ...
```

Best for: validators, parsers, serializers, pure functions.

---

## Framework & Tooling

| Tool | Purpose |
|------|---------|
| `pytest` + `pytest-django` | Main test runner |
| `pytest-cov` | Coverage reporting |
| `pytest-asyncio` | Async test support |
| `pytest-xdist` | Parallel test execution |
| `pytest-mock` | Cleaner mock syntax (optional) |

**Fixtures over setUp/tearDown. Always.**

---

## Recommended Imports

```python
from unittest.mock import (
    patch,
    Mock,
    MagicMock,
    PropertyMock,
    AsyncMock,
    call,
    ANY,
)
import pytest
from pytest_mock import MockerFixture  # if using mocker fixture
```

---

## Mocking Strictness by Layer

| Layer | Mock? | autospec? | Notes |
|-------|-------|-----------|-------|
| External SDKs (Stripe, SendGrid, boto3) | **Always** | Yes (disable if dynamic) | Patch client method/class |
| File system / S3 / storage | **Always** | Yes | Return fake file-like objects |
| Celery / async tasks | **Almost always** | Yes | Patch `.delay()` or task function |
| Django cache / Redis | **Usually** | Yes | Or use `DummyCache` via settings |
| ORM – `Model.objects` | **Rarely** | Yes | Prefer real test DB (see below) |
| Forms / Serializers | **Very rarely** | — | Test real validation |
| Views / Viewsets | **Rarely** | — | Mock services, not the view |
| Signals (your code) | **Rarely** | — | Prefer integration tests |
| Your business logic | **Never** | — | This is what you're testing |

---

## ORM Testing Stance (Clarified)

**Default:** Use real test database. SQLite in-memory is fast enough for most cases.

**Mock selectively only when:**
- Query is a performance killer in tests (complex aggregations, huge joins)
- You need extreme isolation for a specific unit test
- Testing behavior when DB returns unexpected results

**Never do this:**

```python
# ❌ Don't wholesale replace the manager
with patch.object(User, 'objects') as mock_objects:
    mock_objects.filter.return_value.first.return_value = Mock(id=1)
```

**Do this instead:**

```python
# ✅ Create real test data
user = UserFactory(is_active=True)
result = get_active_users()
assert user in result
```

---

## Core Guiding Rules

> **Mock the outside world aggressively**
> External APIs, SDKs, third-party services — always mock.

> **Mock infrastructure reasonably**
> Cache, Celery, file storage — usually mock, sometimes use fakes.

> **Mock Django ORM rarely**
> Use real test database. Mock only for specific isolation needs.

> **Never mock your own business logic**
> If you need to mock your service to test your service, refactor the service.

---

## Quick Decision Tree

```
What do I need to mock?

├─► External API / SDK (Stripe, Twilio, etc.)
│   └─► ALWAYS mock. Use autospec=True (unless client is highly dynamic).

├─► File system / S3 / cloud storage
│   └─► ALWAYS mock. Return fake file objects.

├─► Celery task
│   └─► Mock .delay() → return fake AsyncResult

├─► Redis / cache
│   └─► Use DummyCache in settings OR mock cache.get/set

├─► Django ORM
│   └─► USE REAL TEST DB. Mock only if query is slow or you need isolation.

├─► Datetime / time
│   └─► Use freezegun OR time-machine (pick one for project)

├─► HTTP calls
│   └─► responses (requests) / respx (httpx)

├─► Your own service layer
│   └─► DO NOT MOCK. Test it directly. If untestable, refactor it.

└─► Settings / feature flags
    └─► @override_settings or patch.dict
```

---

## Example: Sync Test with Factory + Mock

```python
"""Tests for orders.services module."""
from unittest.mock import patch, Mock
import pytest

from orders.services import create_order
from orders.factories import UserFactory, ProductFactory


class TestCreateOrder:

    @pytest.mark.django_db
    def test_create_order_when_stock_available_returns_success(self):
        user = UserFactory()
        product = ProductFactory(stock=10)

        result = create_order(user=user, product=product, quantity=2)

        assert result.status == "confirmed"
        product.refresh_from_db()
        assert product.stock == 8

    @pytest.mark.django_db
    @patch("orders.services.stripe.Charge.create", autospec=True)
    def test_create_order_calls_stripe_correctly(self, mock_charge):
        mock_charge.return_value = Mock(id="ch_123", status="succeeded")
        user = UserFactory(stripe_customer_id="cus_abc")
        product = ProductFactory(price=1000, stock=10)

        create_order(user=user, product=product, quantity=2)

        mock_charge.assert_called_once_with(
            amount=2000,
            currency="usd",
            customer="cus_abc",
        )

    @pytest.mark.django_db
    @patch("orders.services.stripe.Charge.create", autospec=True)
    def test_create_order_when_stripe_fails_raises_payment_error(self, mock_charge):
        import stripe
        mock_charge.side_effect = stripe.error.CardError(
            message="declined", param=None, code="card_declined"
        )
        user = UserFactory()
        product = ProductFactory(stock=10)

        with pytest.raises(PaymentError, match="declined"):
            create_order(user=user, product=product, quantity=1)
```

---

## Example: Async Test

```python
from unittest.mock import AsyncMock, patch
import pytest


class TestAsyncNotification:

    @pytest.mark.asyncio
    @pytest.mark.django_db
    @patch("notifications.services.firebase.send", new_callable=AsyncMock)
    async def test_send_push_notification_success(self, mock_send):
        mock_send.return_value = {"message_id": "msg_123"}

        result = await send_push_notification(user_id=1, title="Hello")

        assert result["message_id"] == "msg_123"
        mock_send.assert_called_once()
```

---

## When to Break These Rules

These are **strong defaults**, not laws. Break them when:

- You inherit a 400-line service with 7 dependencies → mock some internals while you refactor
- Third-party SDK changes signatures constantly → disable autospec for that specific mock
- Test DB is genuinely too slow even with SQLite → mock the heaviest queries
- Team agrees on a different convention → document it and be consistent

**Document your exceptions. Don't just "do whatever."**

---

## Usage

Use this as your **primary reference** when:

- Writing new tests
- Reviewing test PRs
- Generating tests with AI/Cursor
- Onboarding new team members

Consistency beats perfection. Follow these conventions until you have a documented reason not to.

