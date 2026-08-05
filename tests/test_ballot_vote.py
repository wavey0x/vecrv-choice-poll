import boa


def test_exact_split_accounting(system, create_ballot):
    ballot = create_ballot()
    voter = system.accounts.voter
    weight = 125 * 10**18
    system.mock.set_balance_at(voter, ballot.reference_block(), weight)

    with boa.env.prank(voter):
        ballot.vote([2_500, 3_000, 4_500])

    assert ballot.has_voted(voter)
    assert ballot.participating_weight() == weight
    assert [ballot.choice_scores(i) for i in range(3)] == [
        weight * 2_500,
        weight * 3_000,
        weight * 4_500,
    ]
    assert ballot.choices() == (
        ["No award", "Team A", "Team B"],
        [weight * 2_500, weight * 3_000, weight * 4_500],
    )
    assert sum(ballot.choice_scores(i) for i in range(3)) == weight * 10_000


def test_second_vote_reverts(system, create_ballot):
    ballot = create_ballot()
    voter = system.accounts.voter
    system.mock.set_balance_at(voter, ballot.reference_block(), 1)

    with boa.env.prank(voter):
        ballot.vote([10_000, 0, 0])
        with boa.reverts("already voted"):
            ballot.vote([0, 10_000, 0])


def test_failed_first_vote_does_not_consume_eligibility(system, create_ballot):
    ballot = create_ballot()
    voter = system.accounts.voter
    system.mock.set_balance_at(voter, ballot.reference_block(), 100)

    with boa.env.prank(voter):
        with boa.reverts("wrong total"):
            ballot.vote([5_000, 0, 0])
        assert not ballot.has_voted(voter)
        ballot.vote([5_000, 5_000, 0])

    assert ballot.has_voted(voter)


def test_invalid_allocations_revert(system, create_ballot):
    ballot = create_ballot()
    voter = system.accounts.voter
    system.mock.set_balance_at(voter, ballot.reference_block(), 100)

    with boa.env.prank(voter):
        with boa.reverts("wrong length"):
            ballot.vote([5_000, 5_000])
        with boa.reverts("allocation too high"):
            ballot.vote([10_001, 0, 0])
        with boa.reverts("wrong total"):
            ballot.vote([5_000, 4_999, 0])
        with boa.reverts("wrong total"):
            ballot.vote([5_000, 5_001, 0])
    assert not ballot.has_voted(voter)


def test_zero_weight_cannot_vote(system, create_ballot):
    ballot = create_ballot()

    with boa.env.prank(system.accounts.voter):
        with boa.reverts("no voting power"):
            ballot.vote([10_000, 0, 0])
    assert not ballot.has_voted(system.accounts.voter)


def test_vote_respects_window(system, create_ballot):
    voter = system.accounts.voter
    start = boa.env.timestamp + 100
    ballot = create_ballot(start_time=start, end_time=start + 100)
    system.mock.set_balance_at(voter, ballot.reference_block(), 100)

    with boa.env.prank(voter):
        with boa.reverts("not started"):
            ballot.vote([10_000, 0, 0])

    boa.env.time_travel(seconds=100)
    with boa.env.prank(voter):
        ballot.vote([10_000, 0, 0])

    second = system.accounts.second_voter
    system.mock.set_balance_at(second, ballot.reference_block(), 100)
    boa.env.time_travel(seconds=100)
    with boa.env.prank(second):
        with boa.reverts("ended"):
            ballot.vote([10_000, 0, 0])


def test_snapshot_weight_is_immutable(system, create_ballot):
    ballot = create_ballot()
    voter = system.accounts.voter
    historical_weight = 75
    system.mock.set_balance_at(voter, ballot.reference_block(), historical_weight)
    system.mock.set_balance(voter, 999_999)

    with boa.env.prank(voter):
        ballot.vote([0, 10_000, 0])

    assert ballot.participating_weight() == historical_weight
