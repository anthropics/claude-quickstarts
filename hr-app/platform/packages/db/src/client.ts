import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

export interface DbConfig {
  connectionString: string;
  /** Postgres schema to set as search_path — either `platform` or `tenant_<id>`. */
  schema: string;
}

export function createTenantDb(config: DbConfig) {
  const pool = new Pool({
    connectionString: config.connectionString,
    options: `-c search_path=${config.schema},public`,
  });
  return drizzle(pool);
}

export function createPlatformDb(connectionString: string) {
  return createTenantDb({ connectionString, schema: "platform" });
}
