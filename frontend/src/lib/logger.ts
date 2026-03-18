type LogLevel = "debug" | "info" | "warn" | "error";

const level: LogLevel =
  (process.env.NEXT_PUBLIC_LOG_LEVEL as LogLevel | undefined) ?? "info";

const isEnabled = (requested: LogLevel) => {
  const order: Record<LogLevel, number> = {
    debug: 10,
    info: 20,
    warn: 30,
    error: 40,
  };
  return order[requested] >= order[level];
};

export const log = {
  debug: (...args: unknown[]) => {
    if (!isEnabled("debug")) return;
    // eslint-disable-next-line no-console
    console.debug(...args);
  },
  info: (...args: unknown[]) => {
    if (!isEnabled("info")) return;
    // eslint-disable-next-line no-console
    console.info(...args);
  },
  warn: (...args: unknown[]) => {
    if (!isEnabled("warn")) return;
    // eslint-disable-next-line no-console
    console.warn(...args);
  },
  error: (...args: unknown[]) => {
    if (!isEnabled("error")) return;
    // eslint-disable-next-line no-console
    console.error(...args);
  },
};

