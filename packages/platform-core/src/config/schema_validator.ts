import AjvLib from "ajv";
import addFormatsLib from "ajv-formats";
import type { ValidateFunction, ErrorObject } from "ajv";

// Handle both ESM default export and CJS module.exports patterns
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Ajv = (AjvLib as any).default ?? AjvLib;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const addFormats = (addFormatsLib as any).default ?? addFormatsLib;

export class ValidationError extends Error {
  constructor(
    message: string,
    public readonly errors: ErrorObject[]
  ) {
    super(message);
    this.name = "ValidationError";
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AjvInstance = any;

export class SchemaValidator {
  private ajv: AjvInstance;
  private validators = new Map<string, ValidateFunction>();

  constructor() {
    this.ajv = new Ajv({ allErrors: true, strict: false });
    addFormats(this.ajv);
  }

  addSchema(id: string, schema: object): void {
    this.ajv.addSchema(schema, id);
    this.validators.set(id, this.ajv.compile(schema));
  }

  validate(schemaId: string, data: unknown): void {
    const validator = this.validators.get(schemaId);
    if (!validator) {
      throw new Error(`No schema registered with id: ${schemaId}`);
    }

    const valid = validator(data);
    if (!valid) {
      const errors = validator.errors ?? [];
      const messages = errors
        .map((e: ErrorObject) => `${e.instancePath || "root"}: ${e.message ?? "invalid"}`)
        .join("; ");
      throw new ValidationError(
        `Config validation failed: ${messages}`,
        errors
      );
    }
  }

  validateWithSchema(schema: object, data: unknown): void {
    const validate = this.ajv.compile(schema);
    const valid = validate(data);
    if (!valid) {
      const errors: ErrorObject[] = validate.errors ?? [];
      const messages = errors
        .map((e: ErrorObject) => `${e.instancePath || "root"}: ${e.message ?? "invalid"}`)
        .join("; ");
      throw new ValidationError(`Validation failed: ${messages}`, errors);
    }
  }

  getAjv(): AjvInstance {
    return this.ajv;
  }
}

export const globalSchemaValidator = new SchemaValidator();
