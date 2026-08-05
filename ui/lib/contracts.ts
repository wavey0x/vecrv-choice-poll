export const factoryAbi = [
  {
    type: "function",
    name: "ballot_count",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "ballots",
    stateMutability: "view",
    inputs: [{ name: "arg0", type: "uint256" }],
    outputs: [{ name: "", type: "address" }],
  },
] as const;

export const ballotAbi = [
  view("title", "string"),
  view("start_time", "uint256"),
  view("end_time", "uint256"),
  view("reference_block", "uint256"),
  view("reference_supply", "uint256"),
  view("quorum_bps", "uint16"),
  view("option_count", "uint16"),
  {
    type: "function",
    name: "choice_name",
    stateMutability: "view",
    inputs: [{ name: "choice_id", type: "uint16" }],
    outputs: [{ name: "", type: "string" }],
  },
  {
    type: "function",
    name: "option_scores",
    stateMutability: "view",
    inputs: [{ name: "arg0", type: "uint256" }],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "participating_weight",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "has_voted",
    stateMutability: "view",
    inputs: [{ name: "arg0", type: "address" }],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    type: "function",
    name: "vote",
    stateMutability: "nonpayable",
    inputs: [{ name: "allocations_bps", type: "uint16[]" }],
    outputs: [],
  },
] as const;

function view(name: string, outputType: string) {
  return {
    type: "function" as const,
    name,
    stateMutability: "view" as const,
    inputs: [] as const,
    outputs: [{ name: "", type: outputType }],
  };
}
