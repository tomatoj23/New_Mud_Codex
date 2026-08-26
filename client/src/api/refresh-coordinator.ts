export interface PendingRefresh {
  slot: "auth-refresh-v1";
  idempotency_key: string;
  endpoint: "/api/v1/auth/refresh";
  state: "pending";
  created_at: string;
}

export interface RefreshResult {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  auth_session_id: string;
  game_account_id: string;
}

export interface RefreshMessage {
  type: "refresh-completed" | "refresh-failed";
  result?: RefreshResult;
  errorCode?: string;
}

interface RefreshChannel {
  onmessage: ((event: MessageEvent<RefreshMessage>) => void) | null;
  postMessage(message: RefreshMessage): void;
  close(): void;
}

export interface RefreshCoordinatorEnvironment {
  openChannel(): RefreshChannel;
  requestLock<T>(callback: (lock: object | null) => Promise<T>): Promise<T>;
  getOrCreatePending(): Promise<PendingRefresh>;
  clearPending(): Promise<void>;
  now(): number;
  ownerWaitMs: number;
}

export class RefreshCoordinationError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "RefreshCoordinationError";
  }
}

class RefreshOwnerUnavailableError extends Error {}

const DATABASE_NAME = "new-mud-auth-control";
const STORE_NAME = "pending-refresh";
const SLOT = "auth-refresh-v1";
const RETRY_WINDOW_MS = 24 * 60 * 60 * 1000;

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: "slot" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB unavailable"));
  });
}

function transact<T>(
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore, setResult: (value: T) => void) => void,
): Promise<T> {
  return openDatabase().then(
    (database) =>
      new Promise<T>((resolve, reject) => {
        let result: T | undefined;
        let hasResult = false;
        const transaction = database.transaction(STORE_NAME, mode);
        operation(transaction.objectStore(STORE_NAME), (value) => {
          result = value;
          hasResult = true;
        });
        transaction.onerror = () => {
          database.close();
          reject(transaction.error ?? new Error("IndexedDB transaction failed"));
        };
        transaction.oncomplete = () => {
          database.close();
          if (!hasResult) {
            reject(new Error("IndexedDB transaction completed without a result"));
            return;
          }
          resolve(result as T);
        };
      }),
  );
}

async function getOrCreatePending(): Promise<PendingRefresh> {
  return transact("readwrite", (store, resolve) => {
    const get = store.get(SLOT);
    get.onsuccess = () => {
      const existing = get.result as PendingRefresh | undefined;
      if (existing) {
        resolve(existing);
        return;
      }
      const pending: PendingRefresh = {
        slot: SLOT,
        idempotency_key: `refresh_${crypto.randomUUID()}`,
        endpoint: "/api/v1/auth/refresh",
        state: "pending",
        created_at: new Date().toISOString(),
      };
      store.put(pending);
      resolve(pending);
    };
  });
}

function clearPending(): Promise<void> {
  return transact("readwrite", (store, resolve) => {
    const deletion = store.delete(SLOT);
    deletion.onsuccess = () => resolve();
  });
}

export function hasPendingRefresh(): Promise<boolean> {
  return transact("readonly", (store, resolve) => {
    const get = store.get(SLOT);
    get.onsuccess = () => resolve(get.result !== undefined);
  });
}

export function clearPendingRefresh(): Promise<void> {
  return clearPending();
}

function waitForOwner(
  channel: RefreshChannel,
  timeoutMs: number,
  acceptResult: (result: RefreshResult) => void,
): Promise<RefreshResult> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new RefreshOwnerUnavailableError()), timeoutMs);
    channel.onmessage = (event: MessageEvent<RefreshMessage>) => {
      clearTimeout(timeout);
      if (event.data.type === "refresh-completed" && event.data.result) {
        acceptResult(event.data.result);
        resolve(event.data.result);
      } else if (event.data.type === "refresh-failed") {
        reject(new RefreshCoordinationError(event.data.errorCode ?? "REFRESH_UNAVAILABLE"));
      }
    };
  });
}

const browserEnvironment: RefreshCoordinatorEnvironment = {
  openChannel: () => new BroadcastChannel(SLOT),
  requestLock: <T>(callback: (lock: object | null) => Promise<T>) =>
    navigator.locks.request(SLOT, { ifAvailable: true }, callback),
  getOrCreatePending,
  clearPending,
  now: () => Date.now(),
  ownerWaitMs: 10_000,
};

function stableErrorCode(error: unknown): string | null {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string"
  ) {
    return error.code;
  }
  return null;
}

async function bestEffortLogout(safeLogout: () => Promise<void>): Promise<void> {
  try {
    await safeLogout();
  } catch {
    // The caller still clears authentication memory; a network failure must not hide the
    // original refresh terminal result.
  }
}

async function refreshAsOwner(
  channel: RefreshChannel,
  send: (idempotencyKey: string) => Promise<RefreshResult>,
  safeLogout: () => Promise<void>,
  acceptResult: (result: RefreshResult) => void,
  environment: RefreshCoordinatorEnvironment,
): Promise<RefreshResult> {
  let pending = await environment.getOrCreatePending();
  try {
    for (;;) {
      const age = environment.now() - Date.parse(pending.created_at);
      if (!Number.isFinite(age) || age > RETRY_WINDOW_MS) {
        await environment.clearPending();
        await bestEffortLogout(safeLogout);
        throw new RefreshCoordinationError("REFRESH_UNAVAILABLE");
      }
      const result = await send(pending.idempotency_key);
      if (result.expires_in <= 0) {
        await environment.clearPending();
        pending = await environment.getOrCreatePending();
        continue;
      }
      acceptResult(result);
      await environment.clearPending();
      channel.postMessage({ type: "refresh-completed", result });
      return result;
    }
  } catch (error) {
    const code = stableErrorCode(error);
    if (code === "REFRESH_IDEMPOTENCY_CONFLICT" || code === "REFRESH_REQUEST_SUPERSEDED") {
      await environment.clearPending();
      await bestEffortLogout(safeLogout);
    } else if (code === "REFRESH_UNAVAILABLE" || code === "SESSION_REVOKED") {
      await environment.clearPending();
    }
    channel.postMessage({ type: "refresh-failed", errorCode: code ?? "REFRESH_UNAVAILABLE" });
    throw error;
  }
}

export async function coordinatedRefresh(
  send: (idempotencyKey: string) => Promise<RefreshResult>,
  safeLogout: () => Promise<void>,
  acceptResult: (result: RefreshResult) => void,
  environment: RefreshCoordinatorEnvironment = browserEnvironment,
): Promise<RefreshResult> {
  for (;;) {
    const channel = environment.openChannel();
    try {
      return await environment.requestLock((lock) =>
        lock
          ? refreshAsOwner(channel, send, safeLogout, acceptResult, environment)
          : waitForOwner(channel, environment.ownerWaitMs, acceptResult),
      );
    } catch (error) {
      if (!(error instanceof RefreshOwnerUnavailableError)) {
        throw error;
      }
    } finally {
      channel.close();
    }
  }
}
