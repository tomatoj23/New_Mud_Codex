import { describe, expect, it } from "vitest";

import protocolErrors from "../../contracts/v1/catalogs/protocol-errors.json";
import protocolCatalog from "../../contracts/v1/catalogs/protocol.json";
import {
  PROTOCOL_ERROR_CODES,
  PROTOCOL_CLIENT_ENVELOPE_FIELDS,
  PROTOCOL_EVENT_TYPES,
  PROTOCOL_REQUEST_TYPES,
  PROTOCOL_SERVER_ENVELOPE_FIELDS,
  PROTOCOL_TERMINAL_TYPES,
  PROTOCOL_VERSION,
} from "../src/protocol/generated";

describe("generated H5 protocol catalog", () => {
  it("matches every protocol value consumed by the client", () => {
    expect([PROTOCOL_VERSION]).toEqual(protocolCatalog.values.protocol_versions);
    expect(PROTOCOL_CLIENT_ENVELOPE_FIELDS).toEqual(
      protocolCatalog.values.client_envelope_fields,
    );
    expect(PROTOCOL_SERVER_ENVELOPE_FIELDS).toEqual(
      protocolCatalog.values.server_envelope_fields,
    );
    expect(PROTOCOL_TERMINAL_TYPES).toEqual(protocolCatalog.values.terminal_types);
    expect(PROTOCOL_REQUEST_TYPES).toEqual(protocolCatalog.values.request_types);
    expect(PROTOCOL_EVENT_TYPES).toEqual(protocolCatalog.values.event_types);
    expect(PROTOCOL_ERROR_CODES).toEqual(
      Object.values(protocolErrors.values).flat().sort(),
    );
  });
});
