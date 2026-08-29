import {
  PROTOCOL_ERROR_CODES,
  PROTOCOL_EVENT_TYPES,
  PROTOCOL_SERVER_ENVELOPE_FIELDS,
  PROTOCOL_TERMINAL_TYPES,
  PROTOCOL_VERSION,
  type ProtocolEventType,
  type ProtocolTerminalType,
} from "./generated";

export interface GameSocket {
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent<string | ArrayBuffer | Blob>) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  send(data: string): void;
  close(code?: number): void;
}

export interface ConnectionAuthenticationSummary {
  authSessionId: string;
  gameAccountId: string;
}

export interface ConnectionStatePort {
  connecting(): void;
  connected(): void;
  authenticating(): void;
  authenticated(summary: ConnectionAuthenticationSummary): void;
  failed(code: string): void;
  disconnected(): void;
}

export interface GameConnectionEnvironment {
  url: string;
  createRequestId(): string;
  createSocket(url: string): GameSocket;
}

export function gameWebSocketUrl(location: Pick<Location, "protocol" | "host">): string {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}/ws/v1/game`;
}

export function browserGameConnectionEnvironment(): GameConnectionEnvironment {
  return {
    url: gameWebSocketUrl(window.location),
    createRequestId: () => `auth-${crypto.randomUUID()}`,
    createSocket: (url) => new WebSocket(url),
  };
}

interface ServerEnvelope {
  version: typeof PROTOCOL_VERSION;
  seq: number;
  ts: string;
  request_id?: string;
  type: ProtocolTerminalType | ProtocolEventType;
  payload: Record<string, unknown>;
}

const AUTHENTICATION_RETRY_MS = 5_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const terminalTypes = new Set<string>(PROTOCOL_TERMINAL_TYPES);
const eventTypes = new Set<string>(PROTOCOL_EVENT_TYPES);
const protocolErrorCodes = new Set<string>(PROTOCOL_ERROR_CODES);

function isServerEnvelope(value: unknown): value is ServerEnvelope {
  if (!isRecord(value)) return false;
  const isTerminal =
    typeof value.type === "string" && terminalTypes.has(value.type);
  const isEvent = typeof value.type === "string" && eventTypes.has(value.type);
  const expectedFields = isTerminal
    ? [...PROTOCOL_SERVER_ENVELOPE_FIELDS, "request_id"].sort()
    : PROTOCOL_SERVER_ENVELOPE_FIELDS;
  return (
    (isTerminal || isEvent) &&
    Object.keys(value).sort().join("\0") === expectedFields.join("\0") &&
    value.version === PROTOCOL_VERSION &&
    Number.isSafeInteger(value.seq) &&
    (value.seq as number) > 0 &&
    typeof value.ts === "string" &&
    (!isTerminal || typeof value.request_id === "string") &&
    isRecord(value.payload)
  );
}

export class GameConnection {
  private socket: GameSocket | null = null;
  private accessToken: string | null = null;
  private authenticationRequestId: string | null = null;
  private authenticationRetryTimer: ReturnType<typeof setTimeout> | null = null;
  private expectedSequence = 1;
  private reconnectAfterClose = false;
  private closeFailureCode: string | null = null;

  constructor(
    private readonly state: ConnectionStatePort,
    private readonly environment: GameConnectionEnvironment,
  ) {}

  connect(accessToken: string) {
    if (this.socket !== null) {
      if (this.accessToken !== accessToken) {
        this.accessToken = accessToken;
        this.reconnectAfterClose = true;
        this.clearAuthenticationRetry();
        this.socket.close(1000);
      }
      return;
    }
    this.accessToken = accessToken;
    this.reconnectAfterClose = false;
    this.openSocket();
  }

  disconnect() {
    const socket = this.socket;
    this.socket = null;
    this.accessToken = null;
    this.authenticationRequestId = null;
    this.reconnectAfterClose = false;
    this.closeFailureCode = null;
    this.clearAuthenticationRetry();
    socket?.close(1000);
    this.state.disconnected();
  }

  private openSocket() {
    this.authenticationRequestId = null;
    this.expectedSequence = 1;
    this.closeFailureCode = null;
    this.state.connecting();
    const socket = this.environment.createSocket(this.environment.url);
    this.socket = socket;
    socket.onopen = () => this.onOpen(socket);
    socket.onmessage = (event) => {
      if (typeof event.data !== "string") {
        this.closeWithFailure(socket, "INVALID_SERVER_ENVELOPE");
        return;
      }
      this.onMessage(socket, event.data);
    };
    socket.onerror = () => this.state.failed("CONNECTION_FAILED");
    socket.onclose = () => {
      if (this.socket === socket) {
        const closeFailureCode = this.closeFailureCode;
        this.socket = null;
        this.closeFailureCode = null;
        this.clearAuthenticationRetry();
        if (this.reconnectAfterClose && this.accessToken !== null) {
          this.reconnectAfterClose = false;
          this.openSocket();
        } else {
          this.state.disconnected();
          if (closeFailureCode !== null) this.state.failed(closeFailureCode);
        }
      }
    };
  }

  private closeWithFailure(socket: GameSocket, code: string) {
    this.closeFailureCode = code;
    this.state.failed(code);
    socket.close(1000);
  }

  private onOpen(socket: GameSocket) {
    if (this.socket !== socket || this.accessToken === null) return;
    this.state.connected();
    this.state.authenticating();
    this.sendAuthentication(socket);
  }

  private sendAuthentication(socket: GameSocket) {
    if (this.socket !== socket || this.accessToken === null) return;
    this.authenticationRequestId ??= this.environment.createRequestId();
    socket.send(
      JSON.stringify({
        version: PROTOCOL_VERSION,
        request_id: this.authenticationRequestId,
        type: "session.authenticate",
        payload: { access_token: this.accessToken },
      }),
    );
    this.clearAuthenticationRetry();
    this.authenticationRetryTimer = setTimeout(
      () => this.sendAuthentication(socket),
      AUTHENTICATION_RETRY_MS,
    );
  }

  private clearAuthenticationRetry() {
    if (this.authenticationRetryTimer !== null) {
      clearTimeout(this.authenticationRetryTimer);
      this.authenticationRetryTimer = null;
    }
  }

  private onMessage(socket: GameSocket, data: string) {
    if (this.socket !== socket) return;
    let envelope: ServerEnvelope;
    try {
      const parsed: unknown = JSON.parse(data);
      if (!isServerEnvelope(parsed)) {
        throw new Error("invalid server envelope");
      }
      envelope = parsed;
    } catch {
      this.closeWithFailure(socket, "INVALID_SERVER_ENVELOPE");
      return;
    }
    if (envelope.seq !== this.expectedSequence) {
      this.clearAuthenticationRetry();
      this.reconnectAfterClose = true;
      this.state.failed("SEQUENCE_GAP");
      socket.close(1000);
      return;
    }
    this.expectedSequence += 1;
    if (envelope.request_id !== this.authenticationRequestId) return;
    if (envelope.payload.request_type !== "session.authenticate") {
      this.closeWithFailure(socket, "INVALID_SERVER_ENVELOPE");
      return;
    }
    if (envelope.type === "request.failed") {
      this.clearAuthenticationRetry();
      const error = isRecord(envelope.payload.error) ? envelope.payload.error : null;
      if (
        error === null ||
        Object.keys(error).sort().join("\0") !== "code\0details\0message\0retryable" ||
        typeof error.code !== "string" ||
        !protocolErrorCodes.has(error.code) ||
        typeof error.message !== "string" ||
        typeof error.retryable !== "boolean" ||
        !isRecord(error.details)
      ) {
        this.closeWithFailure(socket, "INVALID_SERVER_ENVELOPE");
        return;
      }
      this.state.failed(error.code);
      return;
    }
    if (envelope.type !== "request.succeeded") return;
    const result = isRecord(envelope.payload.result) ? envelope.payload.result : {};
    if (
      typeof result.auth_session_id !== "string" ||
      typeof result.game_account_id !== "string"
    ) {
      this.closeWithFailure(socket, "INVALID_SERVER_ENVELOPE");
      return;
    }
    this.clearAuthenticationRetry();
    this.state.authenticated({
      authSessionId: result.auth_session_id,
      gameAccountId: result.game_account_id,
    });
  }
}
