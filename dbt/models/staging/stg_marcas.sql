-- Brand has no master file of its own: it is an attribute of the product,
-- so the entity is derived here, as in the original project.
select distinct
    id_marca,
    marca
from {{ ref('produtos') }}
