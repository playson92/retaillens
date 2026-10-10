# Real report screenshots

These are unchanged, previously executed Power BI Desktop captures, inspected
during portfolio preparation. Each shows **real / olist-v2**, the purchase dates
**2016-09-04 through 2018-10-17** and default/all page slicers. The visible
numbers are rounded for presentation; use the [SQL evidence](../evidence/real/README.md)
for exact values and populations.

| Page | Image | Accepted evidence run |
| --- | --- | --- |
| Overview | [real-overview.png](real-overview.png) | `20261009T2049086587846Z` |
| Deliveries and reviews | [real-deliveries.png](real-deliveries.png) | `20261007T204100Z` |
| Sellers and categories | [real-segments.png](real-segments.png) | `20261007T204100Z` |
| Data quality | [real-quality.png](real-quality.png) | `20261007T204100Z` |

[provenance.json](provenance.json) records original evidence paths, runs,
acceptance reference commits, SHA256, dimensions, source identity, filters and
runtime-record completion times. These times belong to the verification records,
not an invented individual screenshot timestamp. Original bytes match the
archived evidence; no cropping, retouching or new capture was performed.

Overview follows the RL-08 endpoint refresh on 5435. The other pages are from the
earlier accepted four-page model verification on 5433; that historical port is not
the current RetailLens connection instruction. Current Portable uses the resolved
local configuration, `127.0.0.1:5435` in this checkout.
See [final acceptance](../FINAL_ACCEPTANCE.md) for the two acceptance contexts.

Olist and collaborators are the source authors. Real screenshots contain derived
Olist values: the source metadata records **CC BY-NC-SA 4.0** and
[the official dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
This data attribution is separate from the project's MIT code license.
`observation_end=2018-09-01` is assumed; source completeness is not certified.
