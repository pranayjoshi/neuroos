import { readFileSync, watchFile, unwatchFile } from "node:fs";
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";
import { SchemaValidator, ValidationError } from "./schema_validator.js";
import { createLogger } from "../logger.js";

const logger = createLogger("ConfigStore");

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

type WatcherEntry = {
  path: string;
  callback: (value: unknown) => void;
};

export class ConfigStore {
  private config: Record<string, unknown> = {};
  private configPath: string;
  private schemaPath: string;
  private validator: SchemaValidator;
  private watchers: WatcherEntry[] = [];
  private fileWatching = false;

  constructor(configPath = "neuroos.config.yaml") {
    this.configPath = resolve(configPath);
    this.schemaPath = join(__dirname, "../../config/neuroos.config.schema.json");
    this.validator = new SchemaValidator();
  }

  load(): void {
    try {
      const raw = readFileSync(this.configPath, "utf-8");
      const parsed = yaml.load(raw);

      if (typeof parsed !== "object" || parsed === null) {
        throw new Error("Config file must be a YAML object.");
      }

      let schema: object;
      try {
        const schemaRaw = readFileSync(this.schemaPath, "utf-8");
        schema = JSON.parse(schemaRaw) as object;
      } catch {
        const fallbackSchema = join(
          process.cwd(),
          "packages/platform-core/config/neuroos.config.schema.json"
        );
        const schemaRaw = readFileSync(fallbackSchema, "utf-8");
        schema = JSON.parse(schemaRaw) as object;
      }

      this.validator.validateWithSchema(schema, parsed);

      this.config = parsed as Record<string, unknown>;
      logger.info(`Config loaded from: ${this.configPath}`);
    } catch (err) {
      if (err instanceof ValidationError) {
        throw err;
      }
      throw new Error(`Failed to load config from "${this.configPath}": ${String(err)}`);
    }
  }

  get<T>(path: string): T {
    const parts = path.split(".");
    let current: unknown = this.config;

    for (const part of parts) {
      if (typeof current !== "object" || current === null) {
        throw new Error(`Config path not found: "${path}" (failed at "${part}")`);
      }
      current = (current as Record<string, unknown>)[part];
    }

    return current as T;
  }

  set(path: string, value: unknown): void {
    const parts = path.split(".");
    let current = this.config;

    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i]!;
      if (!(part in current) || typeof current[part] !== "object" || current[part] === null) {
        current[part] = {};
      }
      current = current[part] as Record<string, unknown>;
    }

    const lastPart = parts[parts.length - 1]!;
    current[lastPart] = value;

    this.notifyWatchers(path, value);
  }

  watch(path: string, callback: (value: unknown) => void): () => void {
    const entry: WatcherEntry = { path, callback };
    this.watchers.push(entry);

    if (!this.fileWatching) {
      this.startFileWatch();
    }

    return () => {
      const idx = this.watchers.indexOf(entry);
      if (idx !== -1) {
        this.watchers.splice(idx, 1);
      }
    };
  }

  private notifyWatchers(changedPath: string, value: unknown): void {
    for (const watcher of this.watchers) {
      if (changedPath.startsWith(watcher.path) || watcher.path.startsWith(changedPath)) {
        try {
          watcher.callback(value);
        } catch (err) {
          logger.warn(`Config watcher error at path "${watcher.path}": ${String(err)}`);
        }
      }
    }
  }

  private startFileWatch(): void {
    this.fileWatching = true;

    watchFile(this.configPath, { interval: 1000 }, () => {
      logger.info("Config file changed, reloading...");
      try {
        const oldConfig = { ...this.config };
        this.load();

        for (const watcher of this.watchers) {
          try {
            const newValue = this.get(watcher.path);
            watcher.callback(newValue);
          } catch {
            // path may not exist in new config
          }
        }
      } catch (err) {
        logger.error(`Config reload failed: ${String(err)}`);
      }
    });
  }

  stopWatch(): void {
    if (this.fileWatching) {
      unwatchFile(this.configPath);
      this.fileWatching = false;
    }
  }

  getAll(): Record<string, unknown> {
    return { ...this.config };
  }
}

export const globalConfigStore = new ConfigStore(
  process.env["NEUROOS_CONFIG"] ??
    join(process.cwd(), "packages/platform-core/config/neuroos.config.yaml")
);
