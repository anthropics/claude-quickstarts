# Self-hosted sandboxes

Three demos of running managed-agent sessions on infrastructure you
control. All have the same shape: a self-hosted environment
(`config: {type: self_hosted}` in `environments/self-hosted.yaml`) is a work
queue rather than a sandbox template, a host process polls it with the
environment key, and each claimed session runs in its own short-lived
sandbox. The first two use plain Docker containers on the host, the third
uses Archil persistent sandboxes with a shared disk.

- [`docker/`](docker/) is the baseline, all `ant` CLI. The host runs
  `ant beta:worker poll` and each container runs `ant beta:worker run`.
  One credential, the environment key, everywhere, including inside the
  containers. An agent can read its container's environment, so in this
  variant the containers protect the host, not sessions from each other.
- [`docker-memory/`](docker-memory/) adds a memory store. The host side is
  the same CLI poller, and the container runs the Python SDK's
  `EnvironmentWorker`, which downloads the session's memory store to
  `/mnt/memory/...`, syncs edits back, and exits. The environment key never
  enters a container: each one authenticates with a per-session token
  instead, so a session cannot reach another session's work or memories.
- [`archil/`](archil/) runs each session in an [Archil](https://archil.com)
  persistent sandbox (a microVM created through the Archil Python SDK) with
  a 70 GB SEC EDGAR data set mounted as a shared disk. The host side is the
  same CLI poller with a Python `on-work.py`. Every sandbox reads the same
  disk and checks out its own `reports/<session>/` directory for writing,
  so many analyst sessions run in parallel against one copy of the data.

Memory stores mount at a fixed path on the sandbox filesystem, so two
sessions on one unvirtualized machine would read and overwrite each
other's memories. One container per session is the recommended way to run
more than one session per host once memory is attached. The
`docker-memory/` README covers the mechanics.

In all three, the resources are files: the agent under `agents/`, the
environment under `environments/`, and in `docker-memory/` the memory store
under `memory_stores/`.
[`ant apply .`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply)
creates them and records their IDs in `claude-lock.json`, which the scripts
read, and after you edit a file, running it again updates the same
resources. The one manual step is the environment key, which you mint in the
Console for the environment `ant apply` created.
