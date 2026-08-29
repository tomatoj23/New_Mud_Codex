import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  GameConnection,
  gameWebSocketUrl,
  type GameConnectionEnvironment,
  type GameSocket,
} from "../src/protocol/game-connection";
import { useConnectionStore } from "../src/stores/connection";

class FakeGameSocket implements GameSocket {
  readonly sent: string[] = [];
  readonly closeCodes: number[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string | ArrayBuffer | Blob>) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  open() {
    this.onopen?.(new Event("open"));
  }

  receive(message: object) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  send(data: string) {
    this.sent.push(data);
  }

  close(code = 1000) {
    this.closeCodes.push(code);
    this.onclose?.(new CloseEvent("close", { code }));
  }
}

describe("GameConnection", () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => vi.useRealTimers());

  it("uses the fixed game endpoint on the current browser origin", () => {
    expect(gameWebSocketUrl({ protocol: "https:", host: "mud.example" })).toBe(
      "wss://mud.example/ws/v1/game",
    );
    expect(gameWebSocketUrl({ protocol: "http:", host: "localhost:5173" })).toBe(
      "ws://localhost:5173/ws/v1/game",
    );
  });

  it("authenticates a browser WebSocket and stores only the safe session summary", () => {
    const sockets: FakeGameSocket[] = [];
    const environment: GameConnectionEnvironment = {
      url: "ws://example.test/ws/v1/game",
      createRequestId: () => "req-browser-auth",
      createSocket: () => {
        const socket = new FakeGameSocket();
        sockets.push(socket);
        return socket;
      },
    };
    const store = useConnectionStore();
    const connection = new GameConnection(store, environment);

    connection.connect("access-secret");
    expect(store.connectionState).toBe("connecting");
    sockets[0].open();

    expect(store.connectionState).toBe("connected");
    expect(store.authenticationState).toBe("authenticating");
    expect(JSON.parse(sockets[0].sent[0])).toEqual({
      version: "1",
      request_id: "req-browser-auth",
      type: "session.authenticate",
      payload: { access_token: "access-secret" },
    });

    sockets[0].receive({
      version: "1",
      seq: 1,
      ts: "2026-08-29T00:00:00.000Z",
      request_id: "req-browser-auth",
      type: "request.succeeded",
      payload: {
        request_type: "session.authenticate",
        result: {
          auth_session_id: "session-1",
          game_account_id: "account-1",
          user_id: "user-1",
          state: "active",
        },
      },
    });

    expect(store.authenticationState).toBe("authenticated");
    expect(store.authSessionId).toBe("session-1");
    expect(store.gameAccountId).toBe("account-1");
    expect(JSON.stringify(store.$state)).not.toContain("access-secret");
    expect(JSON.stringify(store.$state)).not.toContain("request.succeeded");
  });

  it.each([
    {
      name: "missing protocol version",
      envelope: {
        seq: 1,
        ts: "2026-08-29T00:00:00.000Z",
        request_id: "req-invalid-server-envelope",
        type: "request.succeeded",
        payload: {
          request_type: "session.authenticate",
          result: { auth_session_id: "session-1", game_account_id: "account-1" },
        },
      },
    },
    {
      name: "wrong request type",
      envelope: {
        version: "1",
        seq: 1,
        ts: "2026-08-29T00:00:00.000Z",
        request_id: "req-invalid-server-envelope",
        type: "request.succeeded",
        payload: {
          request_type: "session.ping",
          result: { auth_session_id: "session-1", game_account_id: "account-1" },
        },
      },
    },
    {
      name: "malformed failure payload",
      envelope: {
        version: "1",
        seq: 1,
        ts: "2026-08-29T00:00:00.000Z",
        request_id: "req-invalid-server-envelope",
        type: "request.failed",
        payload: {
          request_type: "session.ping",
          error: { code: "TOKEN_INVALID" },
        },
      },
    },
    {
      name: "unknown error code",
      envelope: {
        version: "1",
        seq: 1,
        ts: "2026-08-29T00:00:00.000Z",
        request_id: "req-invalid-server-envelope",
        type: "request.failed",
        payload: {
          request_type: "session.authenticate",
          error: {
            code: "UNKNOWN_SERVER_ERROR",
            message: "UNKNOWN_SERVER_ERROR",
            retryable: false,
            details: {},
          },
        },
      },
    },
  ])("rejects an authentication terminal with $name", ({ envelope }) => {
    const sockets: FakeGameSocket[] = [];
    const environment: GameConnectionEnvironment = {
      url: "ws://example.test/ws/v1/game",
      createRequestId: () => "req-invalid-server-envelope",
      createSocket: () => {
        const socket = new FakeGameSocket();
        sockets.push(socket);
        return socket;
      },
    };
    const store = useConnectionStore();
    const connection = new GameConnection(store, environment);

    connection.connect("access-secret");
    sockets[0].open();
    sockets[0].receive(envelope);

    expect(store.authenticationState).toBe("unauthenticated");
    expect(store.lastErrorCode).toBe("INVALID_SERVER_ENVELOPE");
    expect(sockets[0].closeCodes).toEqual([1000]);
  });

  it("reuses the authentication request on one socket and creates a new one after a seq gap", () => {
    vi.useFakeTimers();
    const sockets: FakeGameSocket[] = [];
    const requestIds = ["req-first-connection", "req-second-connection"];
    const environment: GameConnectionEnvironment = {
      url: "ws://example.test/ws/v1/game",
      createRequestId: () => requestIds.shift() ?? "unexpected-request-id",
      createSocket: () => {
        const socket = new FakeGameSocket();
        sockets.push(socket);
        return socket;
      },
    };
    const store = useConnectionStore();
    const connection = new GameConnection(store, environment);

    connection.connect("access-secret");
    sockets[0].open();
    vi.advanceTimersByTime(5_000);

    expect(sockets[0].sent).toHaveLength(2);
    expect(JSON.parse(sockets[0].sent[1]).request_id).toBe("req-first-connection");

    sockets[0].receive({
      version: "1",
      seq: 2,
      ts: "2026-08-29T00:00:00.000Z",
      request_id: "req-first-connection",
      type: "request.succeeded",
      payload: { request_type: "session.authenticate", result: {} },
    });

    expect(sockets[0].closeCodes).toEqual([1000]);
    expect(sockets).toHaveLength(2);
    expect(store.connectionState).toBe("connecting");
    sockets[1].open();
    expect(JSON.parse(sockets[1].sent[0]).request_id).toBe("req-second-connection");
  });

  it("reconnects once with a refreshed token and disconnects locally", () => {
    vi.useFakeTimers();
    const sockets: FakeGameSocket[] = [];
    const environment: GameConnectionEnvironment = {
      url: "ws://example.test/ws/v1/game",
      createRequestId: () => "req-current-connection",
      createSocket: () => {
        const socket = new FakeGameSocket();
        sockets.push(socket);
        return socket;
      },
    };
    const store = useConnectionStore();
    const connection = new GameConnection(store, environment);

    connection.connect("access-secret-1");
    sockets[0].open();
    connection.connect("access-secret-2");

    expect(sockets).toHaveLength(2);
    expect(sockets[0].closeCodes).toEqual([1000]);
    sockets[1].open();
    expect(JSON.parse(sockets[1].sent[0]).payload).toEqual({
      access_token: "access-secret-2",
    });
    connection.disconnect();
    vi.advanceTimersByTime(5_000);
    expect(sockets[0].sent).toHaveLength(1);
    expect(sockets[1].closeCodes).toEqual([1000]);
    expect(store.connectionState).toBe("disconnected");
    expect(JSON.stringify(store.$state)).not.toContain("access-secret");
  });
});
