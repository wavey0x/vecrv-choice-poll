#pragma version 0.4.3
#pragma evm-version cancun
#pragma optimize gas

CURVE_OWNERSHIP_AGENT: constant(address) = 0x40907540d8a6C65c637785e8f8B742ae6b0b9968

MAX_CHOICES: constant(uint256) = 15
MAX_INITIAL_CREATORS: constant(uint256) = 8
DEFAULT_VOTING_DURATION: constant(uint256) = 7 * 86400

event CreatorApprovalUpdated:
    creator: indexed(address)
    approved: bool

event BallotCreated:
    ballot_id: indexed(uint256)
    ballot: indexed(address)
    creator: indexed(address)

BALLOT_BLUEPRINT: immutable(address)

ballot_count: public(uint256)
ballots: public(HashMap[uint256, address])
approved_creators: public(HashMap[address, bool])


@deploy
def __init__(
    ballot_blueprint: address,
    initial_creators: DynArray[address, MAX_INITIAL_CREATORS],
):
    assert ballot_blueprint != empty(address), "zero blueprint"
    assert ballot_blueprint.is_contract, "invalid blueprint"
    assert len(initial_creators) > 0, "no creators"

    BALLOT_BLUEPRINT = ballot_blueprint
    self.approved_creators[CURVE_OWNERSHIP_AGENT] = True
    log CreatorApprovalUpdated(creator=CURVE_OWNERSHIP_AGENT, approved=True)

    for i: uint256 in range(MAX_INITIAL_CREATORS):
        if i == len(initial_creators):
            break
        creator: address = initial_creators[i]
        assert creator != empty(address), "zero creator"
        assert creator != CURVE_OWNERSHIP_AGENT, "agent duplicate"
        for j: uint256 in range(MAX_INITIAL_CREATORS):
            if j == i:
                break
            assert creator != initial_creators[j], "duplicate creator"
        self.approved_creators[creator] = True
        log CreatorApprovalUpdated(creator=creator, approved=True)


@external
@view
def ballot_blueprint() -> address:
    return BALLOT_BLUEPRINT


@external
def set_creator(creator: address, approved: bool):
    assert msg.sender == CURVE_OWNERSHIP_AGENT, "not agent"
    assert creator != empty(address), "zero creator"
    assert creator != CURVE_OWNERSHIP_AGENT, "agent permanent"
    assert self.approved_creators[creator] != approved, "no change"

    self.approved_creators[creator] = approved
    log CreatorApprovalUpdated(creator=creator, approved=approved)


@external
def create_ballot(
    title: String[64],
    quorum_bps: uint16,
    choice_names: DynArray[String[64], MAX_CHOICES],
    start_time: uint256 = 0,
    end_time: uint256 = 0,
) -> address:
    assert self.approved_creators[msg.sender], "not creator"

    resolved_start: uint256 = start_time
    if resolved_start == 0:
        resolved_start = block.timestamp

    resolved_end: uint256 = end_time
    if resolved_end == 0:
        assert resolved_start <= max_value(uint256) - DEFAULT_VOTING_DURATION, "window overflow"
        resolved_end = resolved_start + DEFAULT_VOTING_DURATION

    ballot: address = create_from_blueprint(
        BALLOT_BLUEPRINT,
        title,
        resolved_start,
        resolved_end,
        quorum_bps,
        choice_names,
        code_offset=3,
    )

    ballot_id: uint256 = self.ballot_count
    self.ballots[ballot_id] = ballot
    self.ballot_count = ballot_id + 1

    log BallotCreated(ballot_id=ballot_id, ballot=ballot, creator=msg.sender)
    return ballot
