#pragma version 0.4.3
#pragma evm-version cancun
#pragma optimize gas

CURVE_OWNERSHIP_AGENT: constant(address) = 0x40907540d8a6C65c637785e8f8B742ae6b0b9968

MAX_CHOICES: constant(uint256) = 64
MAX_INITIAL_CREATORS: constant(uint256) = 8
DEFAULT_VOTING_DURATION: constant(uint256) = 7 * 86400

event CreatorApprovalUpdated:
    creator: indexed(address)
    approved: bool

event PollCreated:
    poll_id: indexed(uint256)
    poll: indexed(address)
    creator: indexed(address)

POLL_BLUEPRINT: immutable(address)

poll_count: public(uint256)
polls: public(HashMap[uint256, address])
approved_creators: public(HashMap[address, bool])


@deploy
def __init__(
    poll_blueprint: address,
    initial_creators: DynArray[address, MAX_INITIAL_CREATORS],
):
    """
    @notice Create a factory for the supplied poll blueprint.
    @param poll_blueprint ERC-5202 ChoicePoll blueprint address.
    @param initial_creators Addresses initially allowed to create polls.
    """
    assert poll_blueprint != empty(address), "zero blueprint"
    assert poll_blueprint.is_contract, "invalid blueprint"
    assert len(initial_creators) > 0, "no creators"

    POLL_BLUEPRINT = poll_blueprint
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
def poll_blueprint() -> address:
    """
    @notice Return the blueprint used to deploy polls.
    @return ChoicePoll blueprint address.
    """
    return POLL_BLUEPRINT


@external
def set_creator(creator: address, approved: bool):
    """
    @notice Update a poll creator's approval.
    @param creator Address whose approval is being updated.
    @param approved New approval state.
    """
    assert msg.sender == CURVE_OWNERSHIP_AGENT, "not agent"
    assert creator != empty(address), "zero creator"
    assert creator != CURVE_OWNERSHIP_AGENT, "agent permanent"
    assert self.approved_creators[creator] != approved, "no change"

    self.approved_creators[creator] = approved
    log CreatorApprovalUpdated(creator=creator, approved=approved)


@external
def create_poll(
    title: String[64],
    quorum_bps: uint16,
    choice_names: DynArray[String[64], MAX_CHOICES],
    start_time: uint256 = 0,
    end_time: uint256 = 0,
) -> address:
    """
    @notice Create and register a poll.
    @param title Poll title.
    @param quorum_bps Required participation in basis points, where 10,000 is 100%.
    @param choice_names Choice labels in choice ID order.
    @param start_time Opening timestamp, or zero to start immediately.
    @param end_time Closing timestamp, or zero for the default duration.
    @return Deployed poll address.
    """
    assert self.approved_creators[msg.sender], "not creator"

    resolved_start: uint256 = start_time
    if resolved_start == 0:
        resolved_start = block.timestamp

    resolved_end: uint256 = end_time
    if resolved_end == 0:
        assert resolved_start <= max_value(uint256) - DEFAULT_VOTING_DURATION, "window overflow"
        resolved_end = resolved_start + DEFAULT_VOTING_DURATION

    poll: address = create_from_blueprint(
        POLL_BLUEPRINT,
        title,
        resolved_start,
        resolved_end,
        quorum_bps,
        choice_names,
        code_offset=3,
    )

    poll_id: uint256 = self.poll_count
    self.polls[poll_id] = poll
    self.poll_count = poll_id + 1

    log PollCreated(poll_id=poll_id, poll=poll, creator=msg.sender)
    return poll
