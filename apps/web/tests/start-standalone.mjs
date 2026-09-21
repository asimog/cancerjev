import { cpSync, mkdirSync } from "node:fs";

const port = process.argv[2] ?? "3100";
process.env.HOSTNAME = "127.0.0.1";
process.env.PORT = port;

mkdirSync(".next/standalone/.next", { recursive: true });
cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
await import("../.next/standalone/server.js");
