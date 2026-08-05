import boa


UPCOMING = 0
ACTIVE = 1
CLOSED = 2


def _vote(system, poll, voter, weight, allocations):
    system.mock.set_balance_at(voter, poll.reference_block(), weight)
    with boa.env.prank(voter):
        poll.vote(allocations)


def test_status_never_reverts_and_tracks_phase(create_poll):
    start = boa.env.timestamp + 100
    poll = create_poll(start_time=start, end_time=start + 100)

    assert poll.status().phase == UPCOMING
    boa.env.time_travel(seconds=100)
    assert poll.status().phase == ACTIVE
    boa.env.time_travel(seconds=100)
    assert poll.status().phase == CLOSED


def test_winner_is_not_final_before_close(system, create_poll):
    system.mock.set_default_supply(100)
    poll = create_poll(quorum_bps=1, choices=["A", "B"])
    _vote(system, poll, system.accounts.voter, 100, [10_000, 0])

    active = poll.status()
    assert active.phase == ACTIVE
    assert active.quorum_met
    assert not active.has_winner

    boa.env.time_travel(seconds=poll.end_time() - boa.env.timestamp)
    closed = poll.status()
    assert closed.phase == CLOSED
    assert closed.quorum_met
    assert not closed.tied
    assert closed.has_winner
    assert closed.winner_id == 0


def test_clear_winner_after_exact_quorum(system, create_poll):
    system.mock.set_default_supply(1_000)
    poll = create_poll(quorum_bps=1_000, choices=["A", "B"])
    _vote(system, poll, system.accounts.voter, 60, [8_000, 2_000])
    _vote(system, poll, system.accounts.second_voter, 40, [5_000, 5_000])

    assert poll.quorum_reached()
    boa.env.time_travel(seconds=poll.end_time() - boa.env.timestamp)

    status = poll.status()
    assert status.quorum_met
    assert not status.tied
    assert status.has_winner
    assert status.winner_id == 0


def test_quorum_counts_full_voter_weight_for_any_split(system, create_poll):
    system.mock.set_default_supply(1_000)
    poll = create_poll(quorum_bps=1_000, choices=["A", "B"])
    _vote(system, poll, system.accounts.voter, 100, [1, 9_999])

    assert poll.quorum_reached()
    assert poll.participating_weight() == 100


def test_quorum_failure_has_no_winner(system, create_poll):
    system.mock.set_default_supply(1_000)
    poll = create_poll(quorum_bps=2_000, choices=["A", "B"])
    _vote(system, poll, system.accounts.voter, 100, [10_000, 0])
    boa.env.time_travel(seconds=poll.end_time() - boa.env.timestamp)

    status = poll.status()
    assert not status.quorum_met
    assert not status.tied
    assert not status.has_winner


def test_exact_tie_has_no_winner(system, create_poll):
    system.mock.set_default_supply(100)
    poll = create_poll(quorum_bps=1, choices=["A", "B", "C"])
    _vote(system, poll, system.accounts.voter, 100, [5_000, 5_000, 0])
    boa.env.time_travel(seconds=poll.end_time() - boa.env.timestamp)

    status = poll.status()
    assert status.quorum_met
    assert status.tied
    assert not status.has_winner


def test_creator_supplied_none_choice_can_win(system, create_poll):
    system.mock.set_default_supply(100)
    poll = create_poll(choices=["Team A", "None of the above"])
    _vote(system, poll, system.accounts.voter, 100, [0, 10_000])
    boa.env.time_travel(seconds=poll.end_time() - boa.env.timestamp)

    status = poll.status()
    assert status.has_winner
    assert status.winner_id == 1


def test_zero_quorum_without_votes_ends_in_tie(system, create_poll):
    poll = create_poll(quorum_bps=0, choices=["A", "B"])
    boa.env.time_travel(seconds=poll.end_time() - boa.env.timestamp)

    status = poll.status()
    assert status.quorum_met
    assert status.tied
    assert not status.has_winner
