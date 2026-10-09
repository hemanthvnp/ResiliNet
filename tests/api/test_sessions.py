"""Session store (change add-rest-api, task 2.1)."""

import pytest
from fastapi import HTTPException

from api.sessions import SessionStore


def test_two_runs_are_isolated():
    store = SessionStore()
    first, second = store.create("a"), store.create("a")
    assert first != second
    with store.locked(first) as session:
        session.state = "changed"
    with store.locked(second) as session:
        assert session.state == "a"


def test_the_oldest_run_is_evicted_at_the_cap():
    store = SessionStore(cap=2)
    first, second = store.create(1), store.create(2)
    with store.locked(first) as session:  # use does not refresh: eviction follows creation, not access
        session.state = 10
    third = store.create(3)
    with pytest.raises(HTTPException) as err:
        with store.locked(first):
            pass
    assert err.value.status_code == 404
    for run_id, state in [(second, 2), (third, 3)]:
        with store.locked(run_id) as session:
            assert session.state == state


def test_a_held_run_does_not_block_another():
    store = SessionStore()
    first, second = store.create(1), store.create(2)
    with store.locked(first):
        with store.locked(second) as session:  # would deadlock under one global lock
            assert session.state == 2


def test_unknown_run_is_404():
    with pytest.raises(HTTPException) as err:
        with SessionStore().locked("nope"):
            pass
    assert err.value.status_code == 404
