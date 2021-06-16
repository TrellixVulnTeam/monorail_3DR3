// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * An enum object mapping gRPC code names to integer codes.
 * Reference: https://github.com/grpc/grpc-go/blob/972dbd2/codes/codes.go#L43
 * @readonly
 * @enum {number}
 */
export const RpcCode = Object.freeze({
  OK: 0,
  CANCELED: 1,
  UNKNOWN: 2,
  INVALID_ARGUMENT: 3,
  DEADLINE_EXCEEDED: 4,
  NOT_FOUND: 5,
  ALREADY_EXISTS: 6,
  PERMISSION_DENIED: 7,
  RESOURCE_EXHAUSTED: 8,
  FAILED_PRECONDITION: 9,
  ABORTED: 10,
  OUT_OF_RANGE: 11,
  UNIMPLEMENTED: 12,
  INTERNAL: 13,
  UNAVAILABLE: 14,
  DATA_LOSS: 15,
  UNAUTHENTICATED: 16
});

const rpcCodeNames: {[key: number]: string} = {};
for (const name in RpcCode) {
  rpcCodeNames[RpcCode[name as keyof typeof RpcCode]] = name;
}

/**
 * Converts a gRPC code integer into its code name.
 * @param rpcCode {number} the RPC code to convert.
 * @return {string|undefined} the code name of the corresponding gRPC code
 * or undefined if not found.
 */
export function rpcCodeToCodeName(rpcCode: number) {
  return rpcCodeNames[rpcCode];
}

export interface PrpcClientOptions {
  // pRPC server host, defaults to current document host.
  host?: string;
  // OAuth 2.0 access token to use in RPC.
  accessToken?: string;
  // If true, use HTTP instead of HTTPS. Defaults to false.
  insecure?: boolean;
  // If supplied, use this function instead of fetch.
  fetchImpl?: typeof fetch;
}

/**
 * Class for interacting with a pRPC API.
 * Protocol: https://godoc.org/go.chromium.org/luci/grpc/prpc
 */
export class PrpcClient {
  public readonly host: string;
  public readonly accessToken: string | null;
  public readonly insecure: boolean;
  public readonly fetchImpl: typeof fetch;

  /**
   * @constructor
   * @param options {Object} with the following (all optional) config options:
   * - host: {string} pRPC server host, defaults to current document host.
   * - accessToken {string} OAuth 2.0 access token to use in RPC.
   * - insecure {boolean} if true, use HTTP instead of HTTPS. Defaults to false.
   * - fetchImpl {function} if supplied, use this function instead of fetch.
   *   Defaults to `window.fetch`.
   */
  public constructor(options: PrpcClientOptions | null = null) {
    options = options || {};
    this.host = options.host || document.location.host;
    this.accessToken = options.accessToken || null;
    this.insecure =
      options.hasOwnProperty("insecure") && Boolean(options.insecure);
    this.fetchImpl = options.fetchImpl || window.fetch.bind(window);
  }

  /**
   * Send an RPC request.
   * @async
   * @param service {string} Full service name, including package name.
   * @param method {string} Service method name.
   * @param message {Object} The protobuf message to send.
   * @param additionalHeaders {Object} Dict of headers to add to the request.
   * Note: because this method is async the following exceptions reject
   * the returned Promise.
   * @throws {TypeError} for invalid arguments.
   * @throws {ProtocolError} when an error happens at the pRPC protocol
   * (HTTP) level.
   * @throws {GrpcError} when the response returns a non-OK gRPC status.
   * @return {Promise<Object>} a promise resolving the response message
   * or rejecting with an error..
   */
  public async call(service: string, method: string, message: object, additionalHeaders?: {[key: string]: string}) {
    if (!service) {
      throw new TypeError("missing required argument: service");
    }
    if (!method) {
      throw new TypeError("missing required argument: method");
    }
    if (!message) {
      throw new TypeError("missing required argument: message");
    }
    if (!(message instanceof Object)) {
      throw new TypeError("argument `message` must be a protobuf object");
    }

    const protocol = this.insecure === true ? "http:" : "https:";
    const url = `${protocol}//${this.host}/prpc/${service}/${method}`;
    const options = this._requestOptions(message, additionalHeaders);

    const response = await this.fetchImpl(url, options);

    if (!response.headers.has("X-Prpc-Grpc-Code")) {
      throw new ProtocolError(
        response.status,
        "Invalid response: no X-Prpc-Grpc-Code response header"
      );
    }

    const rpcCode = Number.parseInt(
      response.headers.get("X-Prpc-Grpc-Code")!,
      10
    );
    if (Number.isNaN(rpcCode)) {
      throw new ProtocolError(
        response.status,
        `Invalid X-Prpc-Grpc-Code response header`
      );
    }

    const XSSIPrefix = ")]}'";
    const rawResponseText = await response.text();

    if (rpcCode !== RpcCode.OK) {
      throw new GrpcError(rpcCode, rawResponseText);
    }

    if (!rawResponseText.startsWith(XSSIPrefix)) {
      throw new ProtocolError(
        response.status,
        `Response body does not start with XSSI prefix: ${XSSIPrefix}`
      );
    }

    return JSON.parse(rawResponseText.substr(XSSIPrefix.length));
  }

  /**
   * @return {Object} the options used in fetch().
   */
  private _requestOptions(message: object, additionalHeaders?: {[key: string]: string}): RequestInit {
    const headers: {[key: string]: string} = {
      accept: "application/json",
      "content-type": "application/json"
    };
    if (additionalHeaders) {
      Object.assign(headers, additionalHeaders);
    }
    if (this.accessToken) {
      headers.authorization = `Bearer ${this.accessToken}`;
    }

    return {
      credentials: "omit",
      method: "POST",
      headers: headers,
      body: JSON.stringify(message)
    };
  }
}

/**
 * Data class representing an error returned from pRPC-gRPC.
 */
export class GrpcError extends Error {
  public readonly codeName: string;

  /**
   * @constructor
   * @param code {number} gRPC code.
   * @param description {string} error message.
   */
  public constructor(public readonly code: number, public readonly description: string) {
    super();
    if (code === null) {
      throw new Error("missing required argument: code");
    }

    this.codeName = rpcCodeToCodeName(code);
  }

  public get message() {
    return `code: ${this.code} (${this.codeName}) desc: ${this.description}`;
  }
}

/**
 * Data class representing a violation of the pRPC protocol.
 */
export class ProtocolError extends Error {
  public constructor(public readonly httpStatus: number, public readonly description: string) {
    super();
    if (httpStatus === null) {
      throw new Error("missing required argument: httpStatus");
    }
  }

  public get message() {
    return `status: ${this.httpStatus} desc: ${this.description}`;
  }
}
