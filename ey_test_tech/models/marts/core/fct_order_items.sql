WITH carts AS (
    SELECT * FROM {{ ref('stg_carts') }}
),

products AS (
    SELECT * FROM {{ ref('stg_products') }}
),

cart_lines AS (
    SELECT
        c.cart_id,
        c.user_id,
        c.cart_date,
        -- Parsing JSON strict typing
        CAST(JSON_VALUE(item, '$.productId') AS INT64) as product_id,
        CAST(JSON_VALUE(item, '$.quantity') AS INT64) as quantity
    FROM carts c,
    UNNEST(c.products_array) as item
)

SELECT
    cl.cart_id,
    cl.user_id,
    cl.product_id,
    cl.cart_date as order_timestamp,
    DATE(cl.cart_date) as order_date,
    cl.quantity,
    p.price as unit_price,
    (cl.quantity * p.price) as gross_revenue

FROM cart_lines cl
-- LEFT JOIN to preserve sales history even if the product is removed from the catalog (Analytical Integrity)
LEFT JOIN products p ON cl.product_id = p.product_id