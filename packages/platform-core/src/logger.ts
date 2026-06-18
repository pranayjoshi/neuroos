import { createLogger as winstonCreateLogger, format, transports } from "winston";

export function createLogger(name: string) {
  return winstonCreateLogger({
    level: process.env["LOG_LEVEL"] ?? "info",
    format: format.combine(
      format.timestamp(),
      format.printf(({ timestamp, level, message }) => {
        return `[${timestamp}] [${level.toUpperCase()}] [${name}] ${message}`;
      })
    ),
    transports: [new transports.Console()],
  });
}
