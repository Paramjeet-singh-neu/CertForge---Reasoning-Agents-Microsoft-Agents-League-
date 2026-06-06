# DP-203 Azure Data Engineer Associate — Skill Deep Dive (Synthetic)

> Synthetic study reference for demonstration only.

## Synapse

Azure Synapse Analytics for large-scale data warehousing and analytics. Topics:
dedicated vs serverless SQL pools, Spark pools, distribution strategies (hash,
round-robin, replicated), PolyBase/COPY for loading, partitioning, and
integrating Synapse Pipelines. Know when to use serverless for ad-hoc querying.

## Stream Analytics

Real-time stream processing. Topics: Azure Stream Analytics jobs, inputs
(Event Hubs, IoT Hub) and outputs, the SQL-like query language, windowing
functions (tumbling, hopping, sliding, session), watermarks and late-arrival
handling, and exactly-once vs at-least-once semantics.

## Data Lake

Azure Data Lake Storage Gen2. Topics: hierarchical namespace, the medallion
architecture (bronze/silver/gold), file formats (Parquet, Delta, Avro),
partitioning for query performance, access control with POSIX ACLs and RBAC,
and lifecycle management for cost.

## Data Factory

Azure Data Factory for orchestration and ETL/ELT. Topics: pipelines,
activities, linked services, datasets, mapping vs wrangling data flows,
integration runtimes, triggers (schedule, tumbling window, event), and
parameterisation for reusable pipelines.

## Databricks

Azure Databricks for collaborative big-data and ML. Topics: clusters and pools,
notebooks, Delta Lake (ACID on the lake, time travel), the Spark execution
model, Unity Catalog for governance, and orchestration via Jobs/Workflows.
