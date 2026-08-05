import boa


def test_maximum_size_creation_and_vote_have_bounded_gas(system):
    choices = [f"Choice {i}" for i in range(64)]
    gas_before_creation = boa.env.get_gas_used()
    with boa.env.prank(system.accounts.creator):
        address = system.factory.create_poll("Maximum poll", 1_000, choices)
    creation_gas = boa.env.get_gas_used() - gas_before_creation

    poll = system.poll_deployer.at(address)
    system.mock.set_balance_at(
        system.accounts.voter,
        poll.reference_block(),
        100 * 10**18,
    )
    gas_before_vote = boa.env.get_gas_used()
    with boa.env.prank(system.accounts.voter):
        poll.vote([0] * 63 + [10_000])
    voting_gas = boa.env.get_gas_used() - gas_before_vote

    assert creation_gas < 5_000_000
    assert voting_gas < 750_000
