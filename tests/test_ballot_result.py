import boa


def _vote(system, ballot, voter, weight, allocations):
    system.mock.set_balance_at(voter, ballot.reference_block(), weight)
    with boa.env.prank(voter):
        ballot.vote(allocations)


def test_result_reverts_until_window_closes(create_ballot):
    ballot = create_ballot()
    with boa.reverts("still active"):
        ballot.result()


def test_clear_winner_after_quorum(system, create_ballot):
    system.mock.set_default_supply(1_000)
    ballot = create_ballot(quorum_bps=1_000, choices=["A", "B"])
    _vote(system, ballot, system.accounts.voter, 60, [0, 8_000, 2_000])
    _vote(system, ballot, system.accounts.second_voter, 40, [0, 5_000, 5_000])

    assert ballot.quorum_reached()
    boa.env.time_travel(seconds=ballot.end_time() - boa.env.timestamp)

    assert ballot.result() == (True, False, 1)


def test_abstain_counts_for_quorum_but_cannot_win(system, create_ballot):
    system.mock.set_default_supply(1_000)
    ballot = create_ballot(quorum_bps=1_000, choices=["A", "B"])
    _vote(system, ballot, system.accounts.voter, 100, [9_000, 1_000, 0])

    assert ballot.quorum_reached()
    boa.env.time_travel(seconds=ballot.end_time() - boa.env.timestamp)

    assert ballot.result() == (True, False, 1)


def test_quorum_failure_returns_no_winner(system, create_ballot):
    system.mock.set_default_supply(1_000)
    ballot = create_ballot(quorum_bps=2_000, choices=["A", "B"])
    _vote(system, ballot, system.accounts.voter, 100, [0, 10_000, 0])
    boa.env.time_travel(seconds=ballot.end_time() - boa.env.timestamp)

    assert not ballot.quorum_reached()
    assert ballot.result() == (False, False, 0)


def test_exact_tie_returns_no_winner(system, create_ballot):
    system.mock.set_default_supply(100)
    ballot = create_ballot(quorum_bps=1, choices=["A", "B", "C"])
    _vote(system, ballot, system.accounts.voter, 100, [0, 5_000, 5_000, 0])
    boa.env.time_travel(seconds=ballot.end_time() - boa.env.timestamp)

    assert ballot.result() == (True, True, 0)


def test_all_abstain_is_a_tie_between_eligible_choices(system, create_ballot):
    system.mock.set_default_supply(100)
    ballot = create_ballot(quorum_bps=1, choices=["A", "B"])
    _vote(system, ballot, system.accounts.voter, 100, [10_000, 0, 0])
    boa.env.time_travel(seconds=ballot.end_time() - boa.env.timestamp)

    assert ballot.result() == (True, True, 0)
