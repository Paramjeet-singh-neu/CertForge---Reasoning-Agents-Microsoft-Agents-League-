# AZ-400 Azure DevOps Engineer Expert — Skill Deep Dive (Synthetic)

> Synthetic study reference for demonstration only.

## CI/CD

Continuous integration and delivery with Azure Pipelines. Key exam topics:
multi-stage YAML pipelines, build vs. release stages, pipeline triggers and
gates, artifact publishing and consumption, deployment strategies (blue-green,
canary, rolling), and environment approvals. Know how to secure pipelines with
service connections and variable groups backed by Azure Key Vault.

## Monitoring

Observability across the DevOps lifecycle. Topics: Azure Monitor, Application
Insights for application telemetry, Log Analytics with KQL queries, dashboards
and workbooks, alert rules with action groups, and feeding production signals
back into the team's continuous-improvement loop (DevOps feedback).

## GitHub Actions

CI/CD with GitHub Actions as an alternative/complement to Azure Pipelines.
Topics: workflow YAML syntax, events and triggers, jobs and steps, runners
(GitHub-hosted vs self-hosted), reusable workflows, secrets management, and the
GitHub Actions marketplace. Know how Actions integrates with Azure via OIDC.

## Release Management

Managing releases safely at scale. Topics: approvals and gates, deployment
rings, feature flags for progressive exposure, rollback strategies, and change
management. Emphasis on reducing lead time while protecting production stability.

## IaC

Infrastructure as Code. Topics: Bicep and ARM templates, Terraform on Azure,
idempotent deployments, state management, the desired-state model, and
integrating IaC into pipelines so environments are reproducible and auditable.
