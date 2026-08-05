import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createPublicClient,
  createWalletClient,
  custom,
  formatUnits,
  getAddress,
  http,
  isAddress,
  type Address,
} from "viem";
import { mainnet } from "viem/chains";
import { ballotAbi, factoryAbi } from "../lib/contracts";
import { useWallet } from "../lib/useWallet";

const RPC_URL =
  import.meta.env.VITE_ETHEREUM_RPC_URL ||
  "https://eth.drpc.org";
const configuredFactory = import.meta.env.VITE_FACTORY_ADDRESS || "";
const FACTORY_ADDRESS: Address | null = isAddress(configuredFactory)
  ? getAddress(configuredFactory)
  : null;
const MAX_BALLOTS = 50n;

const publicClient = createPublicClient({
  chain: mainnet,
  transport: http(RPC_URL, {
    batch: { batchSize: 100, wait: 16 },
    retryCount: 2,
    timeout: 12_000,
  }),
});

type Ballot = {
  id: bigint;
  address: Address;
  title: string;
  startTime: bigint;
  endTime: bigint;
  referenceBlock: bigint;
  referenceSupply: bigint;
  quorumBps: number;
  participatingWeight: bigint;
  labels: string[];
  scores: bigint[];
  hasVoted: boolean;
};

function compactAddress(address: string) {
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

function timestampLabel(timestamp: bigint) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(Number(timestamp) * 1_000));
}

function veCrv(value: bigint) {
  const formatted = Number.parseFloat(formatUnits(value, 18));
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: formatted < 1_000 ? 2 : 0,
  }).format(formatted);
}

function veCrvScore(value: bigint) {
  const formatted = Number.parseFloat(formatUnits(value, 22));
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: formatted < 1_000 ? 2 : 0,
  }).format(formatted);
}

function ballotStatus(ballot: Ballot, now: number) {
  if (now < Number(ballot.startTime)) return "upcoming";
  if (now >= Number(ballot.endTime)) return "closed";
  return "active";
}

function readableError(error: unknown) {
  if (typeof error === "object" && error) {
    const value = error as { shortMessage?: string; message?: string; code?: number };
    if (value.code === 4001) return "The wallet request was rejected.";
    if (value.shortMessage) return value.shortMessage;
    if (value.message) return value.message.split("\n")[0];
  }
  return "The request could not be completed.";
}

async function readBallot(id: bigint, address: Address, account: Address | null) {
  const contract = { address, abi: ballotAbi } as const;
  const [
    title,
    startTime,
    endTime,
    referenceBlock,
    referenceSupply,
    quorumBps,
    optionCount,
    participatingWeight,
    hasVoted,
  ] = await Promise.all([
    publicClient.readContract({ ...contract, functionName: "title" }),
    publicClient.readContract({ ...contract, functionName: "start_time" }),
    publicClient.readContract({ ...contract, functionName: "end_time" }),
    publicClient.readContract({ ...contract, functionName: "reference_block" }),
    publicClient.readContract({ ...contract, functionName: "reference_supply" }),
    publicClient.readContract({ ...contract, functionName: "quorum_bps" }),
    publicClient.readContract({ ...contract, functionName: "option_count" }),
    publicClient.readContract({ ...contract, functionName: "participating_weight" }),
    account
      ? publicClient.readContract({
          ...contract,
          functionName: "has_voted",
          args: [account],
        })
      : Promise.resolve(false),
  ]);

  const optionIds = Array.from({ length: Number(optionCount) }, (_, index) => index);
  const [choiceNames, scores] = await Promise.all([
    Promise.all(
      optionIds.slice(1).map((choiceId) =>
        publicClient.readContract({
          ...contract,
          functionName: "choice_name",
          args: [choiceId],
        }),
      ),
    ),
    Promise.all(
      optionIds.map((optionId) =>
        publicClient.readContract({
          ...contract,
          functionName: "option_scores",
          args: [BigInt(optionId)],
        }),
      ),
    ),
  ]);

  return {
    id,
    address,
    title,
    startTime,
    endTime,
    referenceBlock,
    referenceSupply,
    quorumBps: Number(quorumBps),
    participatingWeight,
    labels: ["Abstain", ...choiceNames],
    scores,
    hasVoted,
  } satisfies Ballot;
}

export default function Home() {
  const wallet = useWallet(RPC_URL);
  const [ballots, setBallots] = useState<Ballot[]>([]);
  const [selectedAddress, setSelectedAddress] = useState<Address | null>(null);
  const [allocations, setAllocations] = useState<string[]>([]);
  const [loading, setLoading] = useState(Boolean(FACTORY_ADDRESS));
  const [loadError, setLoadError] = useState<string | null>(null);
  const [walletMenu, setWalletMenu] = useState(false);
  const [submitState, setSubmitState] = useState<{
    kind: "idle" | "pending" | "success" | "error";
    message?: string;
    hash?: Address;
  }>({ kind: "idle" });
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1_000));

  const refresh = useCallback(async () => {
    if (!FACTORY_ADDRESS) return;
    setLoadError(null);
    try {
      const count = await publicClient.readContract({
        address: FACTORY_ADDRESS,
        abi: factoryAbi,
        functionName: "ballot_count",
      });
      const first = count > MAX_BALLOTS ? count - MAX_BALLOTS : 0n;
      const ids = Array.from(
        { length: Number(count - first) },
        (_, index) => count - 1n - BigInt(index),
      );
      const addresses = await Promise.all(
        ids.map((id) =>
          publicClient.readContract({
            address: FACTORY_ADDRESS,
            abi: factoryAbi,
            functionName: "ballots",
            args: [id],
          }),
        ),
      );
      const next = await Promise.all(
        addresses.map((address, index) =>
          readBallot(ids[index], address, wallet.account),
        ),
      );
      setBallots(next);
      const refreshedAt = Math.floor(Date.now() / 1_000);
      const chosenAddress =
        selectedAddress && next.some((ballot) => ballot.address === selectedAddress)
          ? selectedAddress
          : (next.find((ballot) => ballotStatus(ballot, refreshedAt) === "active")
              ?.address ?? next[0]?.address ?? null);
      setSelectedAddress(chosenAddress);
      if (chosenAddress !== selectedAddress) {
        const chosen = next.find((ballot) => ballot.address === chosenAddress);
        setAllocations(chosen ? chosen.labels.map(() => "0") : []);
        setSubmitState({ kind: "idle" });
      }
    } catch (error) {
      setLoadError(readableError(error));
    } finally {
      setLoading(false);
    }
  }, [selectedAddress, wallet.account]);

  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const poll = window.setInterval(() => void refresh(), 15_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(poll);
    };
  }, [refresh]);

  useEffect(() => {
    const clock = window.setInterval(
      () => setNow(Math.floor(Date.now() / 1_000)),
      1_000,
    );
    return () => window.clearInterval(clock);
  }, []);

  const selected =
    ballots.find((ballot) => ballot.address === selectedAddress) ?? null;

  const allocationBps = allocations.map((value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
  });
  const allocationTotal = allocationBps.reduce((sum, value) => sum + value, 0);
  const status = selected ? ballotStatus(selected, now) : null;

  const submitVote = async () => {
    if (!selected || !wallet.provider || !wallet.account) return;
    if (!wallet.isMainnet) {
      await wallet.switchNetwork();
      return;
    }
    setSubmitState({ kind: "pending", message: "Confirm the vote in your wallet." });
    try {
      const simulation = await publicClient.simulateContract({
        address: selected.address,
        abi: ballotAbi,
        functionName: "vote",
        args: [allocationBps],
        account: wallet.account,
      });
      const walletClient = createWalletClient({
        account: wallet.account,
        chain: mainnet,
        transport: custom(wallet.provider),
      });
      const hash = await walletClient.writeContract(simulation.request);
      setSubmitState({
        kind: "pending",
        message: "Vote submitted. Waiting for confirmation.",
        hash,
      });
      await publicClient.waitForTransactionReceipt({ hash });
      setSubmitState({ kind: "success", message: "Vote confirmed.", hash });
      await refresh();
    } catch (error) {
      setSubmitState({ kind: "error", message: readableError(error) });
    }
  };

  const walletAction = () => {
    if (wallet.account && !wallet.isMainnet) return wallet.switchNetwork();
    if (wallet.account) return wallet.disconnect();
    if (wallet.wallets.length > 1) {
      setWalletMenu((open) => !open);
      return;
    }
    return wallet.connect();
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">CRV</span>
          <span>Choice voting</span>
        </div>
        <div className="wallet-control">
          <button
            className="wallet-button"
            type="button"
            onClick={walletAction}
            disabled={wallet.busy}
            title={wallet.account && wallet.isMainnet ? "Disconnect wallet" : undefined}
          >
            {wallet.busy
              ? "Waiting…"
              : wallet.account && !wallet.isMainnet
                ? "Switch to Ethereum"
                : wallet.account
                  ? compactAddress(wallet.account)
                  : "Connect wallet"}
          </button>
          {walletMenu && !wallet.account && (
            <div className="wallet-menu" role="menu" aria-label="Choose a wallet">
              {wallet.wallets.map((option) => (
                <button
                  type="button"
                  role="menuitem"
                  key={option.id}
                  onClick={() => {
                    setWalletMenu(false);
                    wallet.choose(option.id);
                    void wallet.connect(option.id);
                  }}
                >
                  {option.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      <main>
        <section className="intro">
          <div>
            <p className="eyebrow">veCRV preference ballots</p>
            <h1>Allocate your vote across the choices.</h1>
            <p className="intro-copy">
              Each wallet votes once with its veCRV balance at the ballot’s snapshot block.
            </p>
          </div>
          {FACTORY_ADDRESS && (
            <a
              className="factory-link"
              href={`https://etherscan.io/address/${FACTORY_ADDRESS}`}
              target="_blank"
              rel="noreferrer"
            >
              Factory {compactAddress(FACTORY_ADDRESS)} ↗
            </a>
          )}
        </section>

        {(wallet.error || loadError) && (
          <div className="notice error" role="alert">
            {wallet.error || loadError}
          </div>
        )}

        {!FACTORY_ADDRESS ? (
          <section className="empty-state">
            <p className="eyebrow">Deployment pending</p>
            <h2>No factory is configured.</h2>
            <p>Add the canonical factory address to load Curve ballots.</p>
          </section>
        ) : loading ? (
          <section className="empty-state" aria-live="polite">
            <p>Loading ballots…</p>
          </section>
        ) : ballots.length === 0 ? (
          <section className="empty-state">
            <h2>No ballots yet.</h2>
            <p>Approved creators have not published a ballot.</p>
          </section>
        ) : (
          <div className="voting-layout">
            <aside className="ballot-list" aria-label="Ballots">
              <div className="panel-heading">
                <span>Ballots</span>
                <span>{ballots.length}</span>
              </div>
              {ballots.map((ballot) => {
                const itemStatus = ballotStatus(ballot, now);
                return (
                  <button
                    type="button"
                    className={
                      ballot.address === selectedAddress
                        ? "ballot-item selected"
                        : "ballot-item"
                    }
                    key={ballot.address}
                    onClick={() => {
                      setSelectedAddress(ballot.address);
                      setAllocations(ballot.labels.map(() => "0"));
                      setSubmitState({ kind: "idle" });
                    }}
                  >
                    <span className={`status-dot ${itemStatus}`} aria-hidden="true" />
                    <span className="ballot-item-copy">
                      <strong>{ballot.title}</strong>
                      <small>Ballot {ballot.id.toString()} · {itemStatus}</small>
                    </span>
                  </button>
                );
              })}
            </aside>

            {selected && (
              <section className="ballot-detail">
                <div className="ballot-header">
                  <div>
                    <div className={`status-label ${status}`}>{status}</div>
                    <h2>{selected.title}</h2>
                  </div>
                  <a
                    href={`https://etherscan.io/address/${selected.address}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {compactAddress(selected.address)} ↗
                  </a>
                </div>

                <dl className="ballot-meta">
                  <div>
                    <dt>Starts</dt>
                    <dd>{timestampLabel(selected.startTime)}</dd>
                  </div>
                  <div>
                    <dt>Ends</dt>
                    <dd>{timestampLabel(selected.endTime)}</dd>
                  </div>
                  <div>
                    <dt>Snapshot</dt>
                    <dd>{selected.referenceBlock.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Quorum</dt>
                    <dd>{(selected.quorumBps / 100).toFixed(2).replace(/\.00$/, "")}%</dd>
                  </div>
                </dl>

                <Results ballot={selected} />

                <div className="allocation-section">
                  <div className="section-heading">
                    <div>
                      <p className="eyebrow">Your allocation</p>
                      <h3>One vote, split any way you choose.</h3>
                    </div>
                    <span className={allocationTotal === 10_000 ? "total valid" : "total"}>
                      {(allocationTotal / 100).toFixed(2)} / 100%
                    </span>
                  </div>

                  <div className="allocation-grid">
                    {selected.labels.map((label, index) => (
                      <label className="allocation-row" key={`${index}-${label}`}>
                        <span>
                          <small>{index === 0 ? "ABSTAIN" : `CHOICE ${index}`}</small>
                          {label}
                        </span>
                        <span className="percent-input">
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.01"
                            inputMode="decimal"
                            value={allocations[index] ?? "0"}
                            disabled={status !== "active" || selected.hasVoted}
                            onChange={(event) => {
                              const value = event.target.value;
                              if (Number(value) > 100 || Number(value) < 0) return;
                              setAllocations((current) =>
                                current.map((item, itemIndex) =>
                                  itemIndex === index ? value : item,
                                ),
                              );
                            }}
                            aria-label={`${label} allocation percentage`}
                          />
                          %
                        </span>
                      </label>
                    ))}
                  </div>

                  {selected.hasVoted ? (
                    <div className="vote-complete">This wallet has voted.</div>
                  ) : status !== "active" ? (
                    <div className="vote-complete">
                      {status === "upcoming" ? "Voting has not started." : "Voting is closed."}
                    </div>
                  ) : !wallet.account ? (
                    <button className="vote-button" type="button" onClick={() => void wallet.connect()}>
                      Connect wallet to vote
                    </button>
                  ) : !wallet.isMainnet ? (
                    <button className="vote-button" type="button" onClick={() => void wallet.switchNetwork()}>
                      Switch to Ethereum
                    </button>
                  ) : (
                    <button
                      className="vote-button"
                      type="button"
                      disabled={allocationTotal !== 10_000 || submitState.kind === "pending"}
                      onClick={() => void submitVote()}
                    >
                      {submitState.kind === "pending" ? "Submitting…" : "Cast vote"}
                    </button>
                  )}

                  {submitState.message && (
                    <p className={`transaction-status ${submitState.kind}`} aria-live="polite">
                      {submitState.message}{" "}
                      {submitState.hash && (
                        <a
                          href={`https://etherscan.io/tx/${submitState.hash}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          View transaction ↗
                        </a>
                      )}
                    </p>
                  )}
                </div>
              </section>
            )}
          </div>
        )}

        <p className="disclaimer">
          A ballot records voter preference. Protocol changes still go through Curve governance.
        </p>
      </main>
    </div>
  );
}

function Results({ ballot }: { ballot: Ballot }) {
  const totalScore = useMemo(
    () => ballot.scores.reduce((sum, score) => sum + score, 0n),
    [ballot.scores],
  );
  const quorumProgress =
    ballot.referenceSupply === 0n
      ? 0
      : Number((ballot.participatingWeight * 10_000n) / ballot.referenceSupply) / 100;
  const quorumMet = quorumProgress * 100 >= ballot.quorumBps;

  return (
    <div className="results-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Current results</p>
          <h3>{veCrv(ballot.participatingWeight)} veCRV participating</h3>
        </div>
        <span className={quorumMet ? "quorum met" : "quorum"}>
          {quorumProgress.toFixed(2)}% participation
        </span>
      </div>
      <div className="results-list">
        {ballot.labels.map((label, index) => {
          const score = ballot.scores[index];
          const share = totalScore === 0n ? 0 : Number((score * 10_000n) / totalScore) / 100;
          return (
            <div className="result-row" key={`${index}-${label}`}>
              <div className="result-copy">
                <span>{label}</span>
                <span>{share.toFixed(2)}% · {veCrvScore(score)} veCRV</span>
              </div>
              <div className="result-track" aria-hidden="true">
                <span style={{ width: `${share}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
