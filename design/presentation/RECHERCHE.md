# References and scope

These sources informed the architecture or domain framing. Their results are not performance
claims for this prototype. The prototype's own limitations and results are reported separately.

- [Supporting Industrial Test-Failure Analysis with LLM-Based Systems](https://arxiv.org/abs/2609.21843):
  industrial test-failure investigation and practitioner evaluation; its small study does not establish
  a universal benefit from agents or additional agents.
- [CausalPulse: Agentic Copilot for Root Cause Analysis in Smart Manufacturing](https://arxiv.org/abs/2603.29755):
  planning combined with specialized diagnostic procedures. Workflow execution success is distinct
  from diagnostic accuracy.
- [Abboush, Knieke and Rausch, Scientific Reports](https://www.nature.com/articles/s41598-025-21416-5):
  automotive HiL fault analysis in a CI workflow, not evidence that this LLM prototype outperforms
  classical fault detection.
- [C4 model](https://c4model.com/diagrams): separation of system context and runtime architecture.
- [W3C PROV overview](https://www.w3.org/TR/prov-overview/): provenance concepts; the application
  uses its own reference schema and does not implement a W3C-PROV export.
- [NIST AMS 400-2](https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.400-2.pdf): digital-twin terminology;
  the Twin service here is a stateful simulator without a connected physical asset.
