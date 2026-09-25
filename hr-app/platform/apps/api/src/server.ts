import Fastify from "fastify";

export function buildServer() {
  const app = Fastify({ logger: true });

  app.get("/healthz", async () => ({ status: "ok" }));

  return app;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const app = buildServer();
  const port = Number(process.env.PORT ?? 4000);
  app.listen({ port, host: "0.0.0.0" }).catch((err) => {
    app.log.error(err);
    process.exit(1);
  });
}
