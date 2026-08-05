import boa


def test_exact_split_accounting(system, create_poll):
    poll = create_poll()
    voter = system.accounts.voter
    weight = 125 * 10**18
    system.mock.set_balance_at(voter, poll.snapshot_block(), weight)

    with boa.env.prank(voter):
        poll.vote([2_500, 3_000, 4_500])

    assert poll.has_voted(voter)
    assert poll.voted_supply() == weight
    assert poll.choices() == (
        ["No award", "Team A", "Team B"],
        [weight * 2_500, weight * 3_000, weight * 4_500],
    )
    assert sum(poll.choices()[1]) == weight * 10_000


def test_vote_emits_one_event_per_nonzero_allocation(system, create_poll):
    poll = create_poll()
    voter = system.accounts.voter
    weight = 125 * 10**18
    system.mock.set_balance_at(voter, poll.snapshot_block(), weight)

    with boa.env.prank(voter):
        poll.vote([2_500, 0, 7_500])

    logs = poll.get_logs()
    assert len(logs) == 2
    assert [
        (log.voter, log.choice_id, log.allocation_bps, log.weight)
        for log in logs
    ] == [
        (voter, 0, 2_500, weight),
        (voter, 2, 7_500, weight),
    ]


def test_second_vote_reverts(system, create_poll):
    poll = create_poll()
    voter = system.accounts.voter
    system.mock.set_balance_at(voter, poll.snapshot_block(), 1)

    with boa.env.prank(voter):
        poll.vote([10_000, 0, 0])
        with boa.reverts("already voted"):
            poll.vote([0, 10_000, 0])


def test_failed_first_vote_does_not_consume_eligibility(system, create_poll):
    poll = create_poll()
    voter = system.accounts.voter
    system.mock.set_balance_at(voter, poll.snapshot_block(), 100)

    with boa.env.prank(voter):
        with boa.reverts("wrong total"):
            poll.vote([5_000, 0, 0])
        assert not poll.has_voted(voter)
        poll.vote([5_000, 5_000, 0])

    assert poll.has_voted(voter)


def test_invalid_allocations_revert(system, create_poll):
    poll = create_poll()
    voter = system.accounts.voter
    system.mock.set_balance_at(voter, poll.snapshot_block(), 100)

    with boa.env.prank(voter):
        with boa.reverts("wrong length"):
            poll.vote([5_000, 5_000])
        with boa.reverts("allocation too high"):
            poll.vote([10_001, 0, 0])
        with boa.reverts("wrong total"):
            poll.vote([5_000, 4_999, 0])
        with boa.reverts("wrong total"):
            poll.vote([5_000, 5_001, 0])
    assert not poll.has_voted(voter)


def test_zero_weight_cannot_vote(system, create_poll):
    poll = create_poll()

    with boa.env.prank(system.accounts.voter):
        with boa.reverts("no voting power"):
            poll.vote([10_000, 0, 0])
    assert not poll.has_voted(system.accounts.voter)


def test_vote_respects_window(system, create_poll):
    voter = system.accounts.voter
    start = boa.env.timestamp + 100
    poll = create_poll(start_time=start, end_time=start + 100)
    system.mock.set_balance_at(voter, poll.snapshot_block(), 100)

    with boa.env.prank(voter):
        with boa.reverts("not started"):
            poll.vote([10_000, 0, 0])

    boa.env.time_travel(seconds=100)
    with boa.env.prank(voter):
        poll.vote([10_000, 0, 0])

    second = system.accounts.second_voter
    system.mock.set_balance_at(second, poll.snapshot_block(), 100)
    boa.env.time_travel(seconds=100)
    with boa.env.prank(second):
        with boa.reverts("ended"):
            poll.vote([10_000, 0, 0])


def test_snapshot_weight_is_immutable(system, create_poll):
    poll = create_poll()
    voter = system.accounts.voter
    historical_weight = 75
    system.mock.set_balance_at(voter, poll.snapshot_block(), historical_weight)
    system.mock.set_balance(voter, 999_999)

    with boa.env.prank(voter):
        poll.vote([0, 10_000, 0])

    assert poll.voted_supply() == historical_weight
