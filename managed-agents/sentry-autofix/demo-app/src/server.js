import * as Sentry from "@sentry/node";
import express from "express";
import { orderTotal } from "./checkout.js";

const app = express();
app.use(express.json());

app.get("/healthz", (_req, res) => res.json({ ok: true }));

app.post("/checkout", (req, res) => {
  res.json(orderTotal(req.body));
});

// After the routes, before any other error middleware: reports whatever a
// route throws to Sentry, then lets express send the 500.
Sentry.setupExpressErrorHandler(app);

const port = Number(process.env.PORT ?? 4000);
app.listen(port, () => console.log(`checkout service on http://localhost:${port}`));
