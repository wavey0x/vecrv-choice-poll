import { useCallback, useEffect, useMemo, useState } from "react";
import type { EIP1193Provider } from "viem";

const MAINNET_CHAIN_ID = 1;
const MAINNET_HEX = "0x1";
const LAST_WALLET_KEY = "curve-choice-voting.wallet";

type BrowserProvider = EIP1193Provider & {
  on?: (event: string, listener: (...args: unknown[]) => void) => void;
  removeListener?: (event: string, listener: (...args: unknown[]) => void) => void;
};

export type WalletOption = {
  id: string;
  name: string;
  rdns: string;
  provider: BrowserProvider;
};

type ProviderAnnouncement = CustomEvent<{
  info: { uuid: string; name: string; rdns: string };
  provider: BrowserProvider;
}>;

function parseChainId(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const parsed = Number.parseInt(value, 16);
  return Number.isFinite(parsed) ? parsed : null;
}

function readError(error: unknown): string {
  if (typeof error === "object" && error) {
    const value = error as { code?: number; message?: string };
    if (value.code === 4001) return "The wallet request was rejected.";
    if (value.message) return value.message.split("\n")[0];
  }
  return "The wallet could not complete the request.";
}

export function useWallet(rpcUrl: string) {
  const [wallets, setWallets] = useState<WalletOption[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [account, setAccount] = useState<`0x${string}` | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => wallets.find((wallet) => wallet.id === selectedId) ?? wallets[0] ?? null,
    [selectedId, wallets],
  );

  useEffect(() => {
    const remembered = window.localStorage.getItem(LAST_WALLET_KEY);
    const addWallet = (wallet: WalletOption) => {
      setWallets((current) => {
        if (
          current.some(
            (item) => item.provider === wallet.provider || item.id === wallet.id,
          )
        ) {
          return current;
        }
        return [...current, wallet];
      });
      if (wallet.rdns === remembered) setSelectedId(wallet.id);
    };

    const announce = (event: Event) => {
      const { info, provider } = (event as ProviderAnnouncement).detail;
      addWallet({ id: info.uuid, name: info.name, rdns: info.rdns, provider });
    };

    window.addEventListener("eip6963:announceProvider", announce);
    window.dispatchEvent(new Event("eip6963:requestProvider"));

    const legacy = (window as Window & { ethereum?: BrowserProvider }).ethereum;
    if (legacy) {
      addWallet({
        id: "legacy-injected",
        name: "Browser wallet",
        rdns: "injected",
        provider: legacy,
      });
    }

    return () => window.removeEventListener("eip6963:announceProvider", announce);
  }, []);

  useEffect(() => {
    if (!selected) return;
    let active = true;

    const applyAccounts = (...args: unknown[]) => {
      const accounts = (Array.isArray(args[0]) ? args[0] : []) as string[];
      if (!active) return;
      setAccount((accounts[0] as `0x${string}` | undefined) ?? null);
    };
    const applyChain = (...args: unknown[]) => {
      if (active) setChainId(parseChainId(args[0]));
    };
    const disconnect = () => {
      if (!active) return;
      setAccount(null);
      setChainId(null);
    };

    selected.provider.on?.("accountsChanged", applyAccounts);
    selected.provider.on?.("chainChanged", applyChain);
    selected.provider.on?.("disconnect", disconnect);

    Promise.all([
      selected.provider.request({ method: "eth_accounts" }),
      selected.provider.request({ method: "eth_chainId" }),
    ])
      .then(([accounts, chain]) => {
        applyAccounts(accounts);
        applyChain(chain);
      })
      .catch(() => undefined);

    return () => {
      active = false;
      selected.provider.removeListener?.("accountsChanged", applyAccounts);
      selected.provider.removeListener?.("chainChanged", applyChain);
      selected.provider.removeListener?.("disconnect", disconnect);
    };
  }, [selected]);

  const choose = useCallback((id: string) => {
    setSelectedId(id);
    setError(null);
  }, []);

  const switchToMainnet = useCallback(async () => {
    if (!selected) throw new Error("No browser wallet was found.");
    try {
      await selected.provider.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: MAINNET_HEX }],
      });
    } catch (switchError) {
      const value = switchError as { code?: number };
      if (value.code !== 4902) throw switchError;
      await selected.provider.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: MAINNET_HEX,
            chainName: "Ethereum",
            nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
            rpcUrls: [rpcUrl],
            blockExplorerUrls: ["https://etherscan.io"],
          },
        ],
      });
    }
    setChainId(MAINNET_CHAIN_ID);
  }, [rpcUrl, selected]);

  const connect = useCallback(async (walletId?: string) => {
    const target = walletId
      ? wallets.find((wallet) => wallet.id === walletId) ?? null
      : selected;
    if (!target) {
      setError("No browser wallet was found. Install a wallet extension and reload.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (target.id !== selectedId) setSelectedId(target.id);
      const accounts = (await target.provider.request({
        method: "eth_requestAccounts",
      })) as string[];
      if (!accounts[0]) throw new Error("The wallet returned no account.");
      const currentChain = parseChainId(
        await target.provider.request({ method: "eth_chainId" }),
      );
      setAccount(accounts[0] as `0x${string}`);
      setChainId(currentChain);
      window.localStorage.setItem(LAST_WALLET_KEY, target.rdns);
      if (currentChain !== MAINNET_CHAIN_ID) {
        try {
          await target.provider.request({
            method: "wallet_switchEthereumChain",
            params: [{ chainId: MAINNET_HEX }],
          });
          setChainId(MAINNET_CHAIN_ID);
        } catch (switchError) {
          const value = switchError as { code?: number };
          if (value.code !== 4902) throw switchError;
          await target.provider.request({
            method: "wallet_addEthereumChain",
            params: [
              {
                chainId: MAINNET_HEX,
                chainName: "Ethereum",
                nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
                rpcUrls: [rpcUrl],
                blockExplorerUrls: ["https://etherscan.io"],
              },
            ],
          });
          setChainId(MAINNET_CHAIN_ID);
        }
      }
    } catch (connectionError) {
      setError(readError(connectionError));
    } finally {
      setBusy(false);
    }
  }, [rpcUrl, selected, selectedId, wallets]);

  const switchNetwork = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await switchToMainnet();
    } catch (switchError) {
      setError(readError(switchError));
    } finally {
      setBusy(false);
    }
  }, [switchToMainnet]);

  const disconnect = useCallback(() => {
    window.localStorage.removeItem(LAST_WALLET_KEY);
    setAccount(null);
    setError(null);
  }, []);

  return {
    wallets,
    selected,
    account,
    chainId,
    provider: selected?.provider ?? null,
    busy,
    error,
    choose,
    connect,
    switchNetwork,
    disconnect,
    isMainnet: chainId === MAINNET_CHAIN_ID,
  };
}
