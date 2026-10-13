# dataset

Raw source-reliability lists, downloaded 2026-10-09. Not cleaned yet.

| File | Source | Content |
|---|---|---|
| `lin2023_domain_pc1.csv` | [hauselin/domain-quality-ratings](https://github.com/hauselin/domain-quality-ratings) (`data/domain_pc1.csv`) | 11,520 domains, aggregate quality score `pc1` (0–1, relative) |
| `lin2023_domain_ratings.csv` | same repo (`data/domain_ratings.csv`) | the six individual rating sets behind `pc1` (Ad Fontes, fact-checkers, MBFC, Lewandowsky, Misinfo.me) |
| `wp_rsp.csv` | [Wikipedia: Reliable sources/Perennial sources](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources), revision 1378772250 | 497 sources: status, last discussion year, domains, summary, link to the entry |

Lin et al. (2023), "High level of correspondence across different news domain quality rating sets", *PNAS Nexus*. Wikipedia content is CC BY-SA 4.0.

Known issues (to handle when cleaning): paths and en-dashes in some Lin domains, platform domains (blogspot.com, medium.com) with a single score, and WP:RSP domains with several verdicts by topic or period.
