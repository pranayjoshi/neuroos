import { describe, expect, it } from "vitest";
import {
  ConnectionError,
  DeviceNotFoundError,
  mapHttpError,
  SessionAlreadyActiveError,
  ValidationError,
} from "../src/errors.js";

describe("mapHttpError", () => {
  it("maps device not found", () => {
    const err = mapHttpError(404, { error: "DEVICE_NOT_FOUND", message: "missing" }, "http://localhost:3000");
    expect(err).toBeInstanceOf(DeviceNotFoundError);
  });

  it("maps session already active", () => {
    const err = mapHttpError(409, { error: "SESSION_ALREADY_ACTIVE", message: "busy" }, "http://localhost:3000");
    expect(err).toBeInstanceOf(SessionAlreadyActiveError);
  });

  it("maps validation errors", () => {
    const err = mapHttpError(422, { message: "invalid payload" }, "http://localhost:3000");
    expect(err).toBeInstanceOf(ValidationError);
  });

  it("maps server errors to connection errors", () => {
    const err = mapHttpError(500, { message: "boom" }, "http://localhost:3000");
    expect(err).toBeInstanceOf(ConnectionError);
  });
});

describe("ConnectionError", () => {
  it("includes helpful message", () => {
    const err = new ConnectionError("http://localhost:3000");
    expect(err.message).toContain("http://localhost:3000");
    expect(err.message).toContain("npx neuroos start");
    expect(err.code).toBe("CONNECTION_FAILED");
  });
});
