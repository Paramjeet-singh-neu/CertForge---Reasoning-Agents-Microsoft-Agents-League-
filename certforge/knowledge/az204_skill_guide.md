# AZ-204 Azure Developer Associate — Skill Deep Dive (Synthetic)

> Synthetic study reference for demonstration only.

## Azure Functions

Azure Functions is a serverless compute service for event-driven code. Key exam
topics: trigger and binding types (HTTP, Timer, Queue, Blob), the Consumption vs
Premium hosting plans, and Durable Functions for stateful orchestration
(function chaining, fan-out/fan-in, and the async HTTP pattern). Know when to use
Durable entities versus orchestrations.

## Storage

Azure Storage covers Blob, Queue, Table, and File services. High-value topics:
- Access tiers: Hot, Cool, and Archive — chosen by access frequency and cost.
  Archive is cheapest to store but has rehydration latency before reads.
- Blob lifecycle management policies to automatically move or delete blobs.
- Shared Access Signatures (SAS) for scoped, time-limited access.
- Storage redundancy options (LRS, ZRS, GRS) and their durability trade-offs.

Cost optimisation: infrequently accessed data belongs in Cool or Archive tiers;
lifecycle policies automate tiering so teams don't pay Hot prices for cold data.

## API Development

Building and securing web APIs on Azure App Service and API Management. Topics:
authentication with Microsoft Entra ID, API versioning, rate limiting and
throttling policies, and caching responses to reduce backend load.

## Monitoring

Application Insights and Azure Monitor for telemetry. Topics: custom metrics and
events, distributed tracing across services, Kusto (KQL) queries over logs, and
configuring alert rules with action groups for proactive notification.

## Security

Securing application secrets and identity. Topics: managed identities (system vs
user assigned) so code never stores credentials, Azure Key Vault for secrets and
certificates, and Microsoft Entra ID app registrations with appropriate scopes.
