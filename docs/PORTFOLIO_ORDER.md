# Portfolio execution order

User decision of 7 October 2026: categories B, then C, then D, then A.
This supersedes the earlier recommendation to start with A2 ImportDesk.

Current implementation: B1 RetailLens.

| Category | Projects |
| --- | --- |
| B Data Analyst | B1 RetailLens, B2 RegionLens |
| C Data Scientist | C1 DemandLab, C2 DecisionLab |
| D Data Engineer | D1 ChangeStream Lab, D2 Data Contracts Monitor |
| A Python Developer | A1 OpsFlow, A2 ImportDesk |

The current command authorizes B1 only. Do not initialize the other applications
as part of this run. Their internal priority can be chosen when that category
starts; this table preserves the existing project identifiers.
