from types import SimpleNamespace

import boa
import pytest


VOTING_ESCROW = "0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2"
OWNERSHIP_AGENT = "0x40907540d8a6C65c637785e8f8B742ae6b0b9968"
DEFAULT_SUPPLY = 1_000_000 * 10**18
WEEK = 7 * 86_400


@pytest.fixture(autouse=True)
def clean_chain():
    boa.reset_env()


@pytest.fixture
def accounts():
    return SimpleNamespace(
        deployer=boa.env.generate_address(),
        creator=boa.env.generate_address(),
        second_creator=boa.env.generate_address(),
        voter=boa.env.generate_address(),
        second_voter=boa.env.generate_address(),
        outsider=boa.env.generate_address(),
    )


@pytest.fixture
def system(accounts):
    mock = boa.load(
        "tests/mocks/MockVotingEscrow.vy",
        override_address=VOTING_ESCROW,
    )
    mock.set_default_supply(DEFAULT_SUPPLY)

    poll_deployer = boa.load_partial("contracts/ChoicePoll.vy")
    with boa.env.prank(accounts.deployer):
        blueprint = poll_deployer.deploy_as_blueprint()
        factory = boa.load(
            "contracts/ChoicePollFactory.vy",
            blueprint.address,
            [accounts.creator],
        )

    return SimpleNamespace(
        mock=mock,
        poll_deployer=poll_deployer,
        blueprint=blueprint,
        factory=factory,
        accounts=accounts,
    )


@pytest.fixture
def create_poll(system):
    def create(
        *,
        title="Risk provider preference",
        quorum_bps=1_000,
        choices=None,
        start_time=None,
        end_time=None,
        sender=None,
    ):
        choices = choices or ["No award", "Team A", "Team B"]
        sender = sender or system.accounts.creator

        with boa.env.prank(sender):
            if start_time is None and end_time is None:
                address = system.factory.create_poll(title, quorum_bps, choices)
            elif end_time is None:
                address = system.factory.create_poll(
                    title,
                    quorum_bps,
                    choices,
                    start_time,
                )
            else:
                address = system.factory.create_poll(
                    title,
                    quorum_bps,
                    choices,
                    start_time or 0,
                    end_time,
                )
        return system.poll_deployer.at(address)

    return create
