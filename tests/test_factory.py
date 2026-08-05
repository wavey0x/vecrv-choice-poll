import boa
import pytest

from conftest import OWNERSHIP_AGENT, WEEK


def test_default_window_and_factory_registration(system, create_ballot):
    created_at = boa.env.timestamp
    ballot = create_ballot()

    assert system.factory.ballot_count() == 1
    assert system.factory.ballots(0) == ballot.address
    assert ballot.start_time() == created_at
    assert ballot.end_time() == created_at + WEEK


def test_window_overloads(system, create_ballot):
    future_start = boa.env.timestamp + 3_600
    scheduled = create_ballot(start_time=future_start)
    explicit = create_ballot(
        start_time=future_start + 60,
        end_time=future_start + 7_200,
    )

    assert scheduled.start_time() == future_start
    assert scheduled.end_time() == future_start + WEEK
    assert explicit.start_time() == future_start + 60
    assert explicit.end_time() == future_start + 7_200


def test_zero_start_with_explicit_end_starts_immediately(system, create_ballot):
    created_at = boa.env.timestamp
    ballot = create_ballot(start_time=0, end_time=created_at + 3_600)

    assert ballot.start_time() == created_at
    assert ballot.end_time() == created_at + 3_600


def test_constructor_approves_agent_and_initial_creators(system):
    assert system.factory.approved_creators(OWNERSHIP_AGENT)
    assert system.factory.approved_creators(system.accounts.creator)


def test_factory_constructor_rejects_invalid_creator_lists(system, accounts):
    with boa.reverts("no creators"):
        boa.load("contracts/ChoiceBallotFactory.vy", system.blueprint.address, [])
    with boa.reverts("zero creator"):
        boa.load(
            "contracts/ChoiceBallotFactory.vy",
            system.blueprint.address,
            ["0x0000000000000000000000000000000000000000"],
        )
    with boa.reverts("agent duplicate"):
        boa.load(
            "contracts/ChoiceBallotFactory.vy",
            system.blueprint.address,
            [OWNERSHIP_AGENT],
        )
    with boa.reverts("duplicate creator"):
        boa.load(
            "contracts/ChoiceBallotFactory.vy",
            system.blueprint.address,
            [accounts.creator, accounts.creator],
        )
    with pytest.raises(Exception):
        boa.load(
            "contracts/ChoiceBallotFactory.vy",
            system.blueprint.address,
            [boa.env.generate_address() for _ in range(9)],
        )


def test_factory_constructor_rejects_invalid_blueprint(accounts):
    with boa.reverts("zero blueprint"):
        boa.load(
            "contracts/ChoiceBallotFactory.vy",
            "0x0000000000000000000000000000000000000000",
            [accounts.creator],
        )
    with boa.reverts("invalid blueprint"):
        boa.load(
            "contracts/ChoiceBallotFactory.vy",
            accounts.outsider,
            [accounts.creator],
        )


def test_only_agent_can_mutate_creator_allowlist(system, create_ballot):
    new_creator = system.accounts.second_creator

    with boa.env.prank(system.accounts.creator):
        with boa.reverts("not agent"):
            system.factory.set_creator(new_creator, True)

    with boa.env.prank(OWNERSHIP_AGENT):
        system.factory.set_creator(new_creator, True)
    assert system.factory.approved_creators(new_creator)
    create_ballot(sender=new_creator)

    with boa.env.prank(OWNERSHIP_AGENT):
        system.factory.set_creator(new_creator, False)
    assert not system.factory.approved_creators(new_creator)

    before = system.factory.ballot_count()
    with boa.env.prank(new_creator):
        with boa.reverts("not creator"):
            system.factory.create_ballot("Blocked", 0, ["A", "B"])
    assert system.factory.ballot_count() == before


def test_agent_is_permanent_and_updates_must_change_state(system):
    with boa.env.prank(OWNERSHIP_AGENT):
        with boa.reverts("agent permanent"):
            system.factory.set_creator(OWNERSHIP_AGENT, False)
        with boa.reverts("zero creator"):
            system.factory.set_creator(
                "0x0000000000000000000000000000000000000000",
                True,
            )
        with boa.reverts("no change"):
            system.factory.set_creator(system.accounts.creator, True)


def test_deployer_has_no_implicit_authority(system):
    assert not system.factory.approved_creators(system.accounts.deployer)

    with boa.env.prank(system.accounts.deployer):
        with boa.reverts("not creator"):
            system.factory.create_ballot("Blocked", 0, ["A", "B"])
        with boa.reverts("not agent"):
            system.factory.set_creator(system.accounts.second_creator, True)


def test_failed_creation_does_not_increment_registry(system):
    with boa.env.prank(system.accounts.creator):
        with boa.reverts("empty title"):
            system.factory.create_ballot("", 0, ["A", "B"])
    assert system.factory.ballot_count() == 0


def test_created_ballots_have_independent_storage(system, create_ballot):
    first = create_ballot(choices=["A", "B"])
    second = create_ballot(choices=["C", "D", "E"])
    weight = 50 * 10**18
    system.mock.set_balance_at(
        system.accounts.voter,
        first.reference_block(),
        weight,
    )

    with boa.env.prank(system.accounts.voter):
        first.vote([10_000, 0])

    assert first.participating_weight() == weight
    assert second.participating_weight() == 0
    assert not second.has_voted(system.accounts.voter)
    assert first.choice_name(0) == "A"
    assert second.choice_name(0) == "C"
