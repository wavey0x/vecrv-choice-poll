export const factoryAbi = [
  {
    type: "function",
    name: "poll_count",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "polls",
    stateMutability: "view",
    inputs: [{ name: "arg0", type: "uint256" }],
    outputs: [{ name: "", type: "address" }],
  },
] as const;

export const pollAbi = [
  view("title", "string"),
  view("start_time", "uint256"),
  view("end_time", "uint256"),
  view("snapshot_block", "uint256"),
  view("snapshot_supply", "uint256"),
  view("quorum_bps", "uint16"),
  {
    type: "function",
    name: "choices",
    stateMutability: "view",
    inputs: [],
    outputs: [
      { name: "", type: "string[]" },
      { name: "", type: "uint256[]" },
    ],
  },
  {
    type: "function",
    name: "winner",
    stateMutability: "view",
    inputs: [],
    outputs: [
      { name: "", type: "bool" },
      { name: "", type: "uint16" },
    ],
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
