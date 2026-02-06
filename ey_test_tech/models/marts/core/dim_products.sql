WITH stg_products AS (
    SELECT * FROM {{ ref('stg_products') }}
)

SELECT
    product_id,
    title,
    price as catalog_price,
    category,
    description,
    image_url,
    
    
    rating_rate as average_rating,
    rating_count as review_count

FROM stg_products