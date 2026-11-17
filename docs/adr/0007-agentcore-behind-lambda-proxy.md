# ADR 0007: AgentCore Runtime behind API Gateway and a Lambda proxy

- **Status:** accepted
- **Sources:** `docs/TRD.md` (stack), `specs/0.7-agentcore-echo.md`, `proxy/handler.py`, `infra/`

## Context

The backend is a FastAPI container that needs HTTP for text and WebSocket for voice. It must cost
nothing while idle and must not hand AWS credentials to the browser.

## Decision

The container runs on Bedrock AgentCore Runtime with IAM auth. The browser calls an API Gateway
HTTP API (throttled), which invokes a Lambda proxy. The proxy validates `X-Visitor-Id`, maps the
REST route to an `action` of the runtime's `/invocations` contract and signs the call (SigV4).
For voice, it checks that the visitor owns the session and returns a SigV4-signed WebSocket URL
valid for 5 minutes. All infrastructure is Terraform.

## Consequences

- Nothing is billed while idle: no load balancer, NAT gateway or instance.
- One more hop and one more Lambda in the request path.
- Opening a fresh AgentCore session took about 6.5 s at Gate 0, so the voice screen has an
  explicit "connecting" state.
- The plan B, FastAPI on Lambda behind the same API Gateway, was never needed.
