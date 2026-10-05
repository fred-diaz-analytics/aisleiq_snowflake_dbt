# AisleIQ

Point-of-sale execution analytics (trade marketing) over 100% synthetic data: it measures how products are displayed, priced and signposted in stores, and how field promoters carry out their visits. This repo is the Snowflake + dbt version of AisleIQ, with the same domain as the original Databricks version.

Business terms are kept in Portuguese (the domain language of the original project); technical conventions are in English. Each entry gives the Portuguese term, its meaning in English, and the words to avoid.

## Language

### Field

**PDV**:
Ponto de venda (point of sale): the physical store where execution is measured.
_Avoid_: Store, ponto

**Promotor**:
Fixed field professional responsible for visiting a store and recording the survey.
_Avoid_: Usuário, vendedor

**Visita**:
A promoter's trip to a store on a given day, which produces the attendance record and the survey answers.
_Avoid_: Check-in

**Cadência de visita**:
How often a store is visited: núcleo, semanal, quinzenal, mensal or esporádica.
_Avoid_: Periodicidade

**Atendimento**:
Record of one visit attempt (store entry and exit); the basis for visit compliance and time in store.

### Execution

**Pesquisa de execução**:
The set of answers a promoter records per store, product and question during a visit.

**Indicador**:
Each of the six metrics measured in the survey: presença, ruptura, preço, MPDV, ponto extra, share de gôndola.

**Presença**:
Whether the product is available in the store.

**Ruptura**:
Product listed in the store's assortment but unavailable on the shelf (out of stock).
_Avoid_: Falta, stockout

**MPDV**:
Material de ponto de venda: a communication piece activated in the store.

**Ponto extra**:
Additional display of the product outside the main shelf, counted per visit.

**Share de gôndola**:
Percentage of shelf space occupied by the brand.

**Preço sugerido**:
Reference price per product, with a tolerance band, used as the price target.

### Quality and score

**Resposta válida**:
An answer that passed the quality rules: no sentinel values, within range and not a price outlier.

**Disponibilidade efetiva (OSA)**:
Per-product measure that combines presence and absence of ruptura; an absent product counts as zero.

**Score de execução (Perfect Store)**:
A 0 to 100 score per store, day and product category, combining availability, price, shelf share, extra display and MPDV with fixed weights.

**Valor em risco**:
Estimated weekly sales value of unavailable products, used to prioritize action by impact and not only by score.

**Cobertura de pilares**:
Share of the score's weight that was actually measured, because a pillar with no data drops out of the score.

### Data

**Dado mestre**:
Static, rarely changed reference data (stores, products), fully reloaded on demand.

**Fato diário**:
Data that arrives as one file per day (atendimento, PDV execution).

**Verdade plantada**:
A known effect deliberately injected into the synthetic data, used to prove that the metrics recover it.
