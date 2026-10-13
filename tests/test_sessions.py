"""mvp-2: the in-memory conversation store."""

from belem_converse.sessions import SessionStore


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_same_session_within_ttl():
    clock = FakeClock()
    store = SessionStore(ttl_s=1800, clock=clock)
    session = store.get_or_create("a")
    session.turns_used = 2

    clock.now += 1799

    assert store.get_or_create("a") is session


def test_new_session_after_ttl():
    clock = FakeClock()
    store = SessionStore(ttl_s=1800, clock=clock)
    store.get_or_create("a").turns_used = 2

    clock.now += 1801

    assert store.get_or_create("a").turns_used == 0


def test_idle_time_counts_from_last_use():
    clock = FakeClock()
    store = SessionStore(ttl_s=1800, clock=clock)
    store.get_or_create("a").turns_used = 1
    clock.now += 1000
    store.get_or_create("a")
    clock.now += 1000

    assert store.get_or_create("a").turns_used == 1


def test_lru_evicts_oldest_when_full():
    clock = FakeClock()
    store = SessionStore(max_sessions=2, clock=clock)
    for session_id in ("a", "b"):
        store.get_or_create(session_id).turns_used = 1
        clock.now += 1
    store.get_or_create("a")  # "a" is now the most recently used
    clock.now += 1

    store.get_or_create("c")

    assert len(store) == 2
    assert store.get_or_create("a").turns_used == 1
    assert store.get_or_create("b").turns_used == 0  # evicted, so it starts over


def test_new_session_starts_empty():
    session = SessionStore().get_or_create("a")

    assert session.turns_used == 0
    assert session.last_plan is None
    assert session.ranked_ids == []
    assert session.cursor == 0
