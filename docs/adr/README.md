# Architecture decision records

One decision per file: context, decision, consequences. ADR 0001 is in Portuguese, like the rest
of the project's internal history (specs, PRD, TRD); the others are in English.

| ADR | Decision |
| --- | --- |
| [0001](0001-gate-0.md) | Gate 0: which risky technologies passed validation (Portuguese) |
| [0002](0002-claude-haiku-default-model.md) | Claude Haiku 4.5 on Bedrock is the default model |
| [0003](0003-single-llm-entry-point.md) | `llm.py` is the only module that calls models |
| [0004](0004-model-writes-code-decides.md) | The model writes, the code decides |
| [0005](0005-ready-made-cases-no-upload.md) | The web demo uses 5 ready-made fictitious cases, no CV upload |
| [0006](0006-anonymous-visitor-id.md) | No login; an anonymous visitor id plus quotas |
| [0007](0007-agentcore-behind-lambda-proxy.md) | AgentCore Runtime behind API Gateway and a Lambda proxy |
| [0008](0008-nova-sonic-for-voice.md) | Amazon Nova 2 Sonic for voice, sharing the text tools |
