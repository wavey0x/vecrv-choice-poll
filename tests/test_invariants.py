import boa
from hypothesis import HealthCheck, given, settings, strategies as st


@given(
    weights=st.lists(st.integers(min_value=1, max_value=10**24), min_size=1, max_size=6),
    first=st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=6),
    second=st.lists(st.integers(min_value=0, max_value=10_000), min_size=1, max_size=6),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_aggregate_score_invariant(system, create_poll, weights, first, second):
    count = min(len(weights), len(first), len(second))

    with boa.env.anchor():
        poll = create_poll(choices=["A", "B", "C"])
        expected = [0, 0, 0]
        participating = 0

        for index in range(count):
            voter = boa.env.generate_address()
            weight = weights[index]
            cut_a = min(first[index], second[index])
            cut_b = max(first[index], second[index])
            allocation = [cut_a, cut_b - cut_a, 10_000 - cut_b]
            system.mock.set_balance_at(voter, poll.snapshot_block(), weight)

            with boa.env.prank(voter):
                poll.vote(allocation)

            participating += weight
            for choice_id in range(3):
                expected[choice_id] += weight * allocation[choice_id]

        scores = [poll.choice_scores(i) for i in range(3)]
        assert poll.participating_weight() == participating
        assert scores == expected
        assert sum(scores) == participating * 10_000
