// Loaded with `node --import` so Sentry is initialized before express is
// imported, which is what lets it instrument the framework.
import * as Sentry from "@sentry/node";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.SENTRY_ENVIRONMENT ?? "production",
});
