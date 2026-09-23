# The shared agent and environment for the webhook-started providers

`cloudflare-containers/`, `cloudflare-worker/`, `daytona/`, `modal/`, and
`vercel/` all run the same demo agent against the same self-hosted
environment. Both are declared here, once:

- [`agents/webhook-demo.md`](agents/webhook-demo.md) is the agent. The
  frontmatter is its configuration and the prose is its system prompt.
- [`environments/webhook-demo.yaml`](environments/webhook-demo.yaml) is the
  self-hosted environment, a work queue that the provider you deploy drains.

Create them from this directory. It needs the
[`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart)
1.30 or later and `jq`:

```sh
ant apply .          # shows the plan, creates both once you approve, records their IDs in claude-lock.json
jq -r '.resources["./environments/webhook-demo.yaml"].id' claude-lock.json    # the env_... ID a provider needs
```

Then follow the README of the provider you are deploying. Each one tells you
where that `env_...` ID goes and how to start a test session.

To change the agent later, edit its file and run `ant apply .` again. It
publishes a new version of the same agent, because `claude-lock.json`
remembers which resources these files became. This repository ignores that
file, since every reader creates their own resources. In a project of your
own, commit it.

## Run it from here, not from the parent directory

`ant apply` walks the directory it is given. From
`self-hosted-sandboxes/` it would also create the agents and environments
that `docker/`, `docker-memory/`, and `archil/` declare. It would also leave
`claude-lock.json` in that parent directory, and `ant apply` finds a lockfile
in any directory above the one it runs from. Every demo below would then
record its IDs there, where its own `start.sh` does not look.
