# Common tasks. Run `make help` for the list.
SHELL := /bin/bash
PY ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
AGENTPOLICY := $(BIN)/agentpolicy
PROFILE ?= hello
SIGNER ?= policy-owner@example.com
KEY ?= state/policy-owner.key

# The demo's own policy workspace (make keys creates it). When it exists, every
# target uses it, so running the demo never changes the tracked policy/ tree.
# Remove state/demo to work on policy/ directly; set AGENTPOLICY_CONFIG to choose.
ifeq ($(origin AGENTPOLICY_CONFIG),undefined)
AGENTPOLICY_CONFIG := $(if $(wildcard state/demo/agentpolicy.yaml),$(CURDIR)/state/demo/agentpolicy.yaml)
endif
export AGENTPOLICY_CONFIG
# Fails a target that would read the demo's copy after policy/ was edited.
fresh = @if [ "$(AGENTPOLICY_CONFIG)" = "$(CURDIR)/state/demo/agentpolicy.yaml" ]; then \
	  echo "using the demo's copy of policy/ in state/demo"; \
	  if [ -n "$$(find policy agentpolicy.yaml -type f -newer state/demo/agentpolicy.yaml | head -1)" ]; then \
	    echo "policy/ or agentpolicy.yaml changed since 'make keys' copied it: run 'make keys' again, or remove state/demo to work on policy/ itself" >&2; exit 1; \
	  fi; fi

.PHONY: help apply dev proto test lint keys sign check enforce-check status image openshell-settings dispatcher reviewer demo promote shrink ops-image audit pki gateway-up

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | expand -t 22

dev: ## Create .venv with agentpolicy and its test tools, and generate the gRPC client
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q -r dev-requirements.txt
	$(BIN)/pip install -q --no-deps -e .
	PATH=$(BIN):$$PATH scripts/gen-proto.sh

proto: ## Regenerate the OpenShell gRPC client from third_party/openshell/proto
	PATH=$(BIN):$$PATH scripts/gen-proto.sh

test: ## Run the unit and command-line tests (no OpenShell, no API access needed)
	$(BIN)/python -m pytest -q

lint: ## Lint the shell scripts
	shellcheck -x start.sh dispatcher/*.sh ../openshell/on-work.sh stack/*.sh examples/*/*.sh scripts/*.sh scripts/ops

keys: ## Demo only: copy policy/ to state/demo, trust a local key there, and sign every ceiling
	AGENTPOLICY=$(AGENTPOLICY) KEY=$(KEY) SIGNER=$(SIGNER) scripts/demo-keys.sh

sign: ## Sign one profile's ceiling: make sign PROFILE=hello KEY=path SIGNER=you@corp
	$(fresh)
	$(AGENTPOLICY) ceiling sign --profile $(PROFILE) --key $(KEY) --identity $(SIGNER)

check: ## Verify every ceiling and prove every profile's grants inside it
	$(fresh)
	$(AGENTPOLICY) check

enforce-check: ## Check on this host that OpenShell enforces host, program, method and path limits (needs the gateway and image)
	AGENTPOLICY=$(AGENTPOLICY) PROFILE=$(PROFILE) scripts/enforce-check.sh

status: ## Summarize profiles and the ledger
	$(AGENTPOLICY) status

apply: ## Create the demo and reviewer agents and their environments with `ant apply`, and map the worker environment to hello
	ant apply $(ANT_FLAGS) agents environments  # named, so the skills under sandbox/ are not taken for resources
	env_id="$$(jq -r '.resources["./environments/worker.yaml"].id // empty' claude-lock.json)"; \
	  [ -n "$$env_id" ] || { echo "no worker environment in claude-lock.json" >&2; exit 1; }; \
	  $(AGENTPOLICY) environment set "$$env_id" hello



image: ## Build ../openshell's image and the sandbox image on the Docker engine OpenShell uses
	docker build -t shs-openshell ../openshell
	docker build -t localhost/shs-openshell-policy:latest sandbox/

openshell-settings: ## Apply the gateway settings this design needs
	stack/openshell-settings.sh

# How long a sandbox outlives its session's last turn. Short for the demo, so
# each session's worker exits soon after its answer; longer in real use.
SANDBOX_MAX_IDLE ?= 15s

dispatcher: ## Run one poller (one concurrent session); run more for more
	PATH=$(BIN):$$PATH SKIP_BUILD=1 SANDBOX_MAX_IDLE=$(SANDBOX_MAX_IDLE) ./start.sh

reviewer: ## Decide pending proposals as they arrive
	PATH=$(BIN):$$PATH $(AGENTPOLICY) grow --interval 2

audit: ## Collect every worker sandbox's allowed decisions from the gateway (evidence for promote and shrink), and its denied ones
	PATH=$(BIN):$$PATH $(AGENTPOLICY) collect-audit

demo: ## Run the hello-world sessions (needs the dispatcher, reviewer and audit running)
	PATH=$(BIN):$$PATH examples/hello-world/run.sh

promote: ## Show what promote would add to PROFILE (add APPLY=1 to write)
	$(AGENTPOLICY) promote --profile $(PROFILE) $(if $(APPLY),--apply)

shrink: ## Show what shrink would remove from PROFILE (add APPLY=1 to write)
	$(AGENTPOLICY) shrink --profile $(PROFILE) $(if $(APPLY),--apply)

# A pip.conf naming your package mirror, passed as a build secret and never
# stored in the image. Required: set PUBLIC_INDEX=1 to build from PyPI
# deliberately instead. The image's packages are hash-locked either way.
PIP_CONF ?= $(HOME)/.config/pip/pip.conf
PIP_SECRET = --secret id=pipconf,src=$(PIP_CONF)

ops-image: ## Build the ops container (scripts/ops) from your mirror (PIP_CONF); PUBLIC_INDEX=1 allows PyPI
	@test -f "$(PIP_CONF)" || test "$(PUBLIC_INDEX)" = 1 || { echo "no pip mirror config at $(PIP_CONF): set PIP_CONF, or PUBLIC_INDEX=1 to build from PyPI" >&2; exit 1; }
	docker build $(if $(wildcard $(PIP_CONF)),$(PIP_SECRET)) -t openshell-policy-ops ops/

# ---- OpenShell as containers, for hosts that cannot run its release binaries

OPENSHELL_GATEWAY_IMAGE ?= ghcr.io/nvidia/openshell/gateway:0.1.2

pki: ## Create the containerized gateway's mTLS PKI and JWT key in state/openshell (once)
	@test ! -e state/openshell/pki/ca.crt || { echo "state/openshell/pki exists; remove it first to start over" >&2; exit 1; }
	mkdir -p state/openshell
	docker run --rm --user "$$(id -u):$$(id -g)" -v "$(CURDIR)/state/openshell:/out" $(OPENSHELL_GATEWAY_IMAGE) \
	  generate-certs --output-dir /out/pki --server-san 127.0.0.1 --server-san localhost
	chmod -R go-rwx state/openshell

gateway-up: ## Start the containerized gateway (stack/openshell) and register it for scripts/ops
	docker compose -f stack/openshell/docker-compose.yml up -d
	scripts/gateway-register.sh
