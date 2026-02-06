WITH source AS (
    SELECT * FROM {{ source('fake_store', 'products_raw') }}
),

latest_run AS (
    SELECT * FROM source 
    QUALIFY ROW_NUMBER() OVER (ORDER BY extracted_at DESC) = 1
),

flattened AS (
    SELECT
        
        CAST(JSON_VALUE(item, '$.id') AS INT64) as product_id,
        JSON_VALUE(item, '$.title') as title,
        JSON_VALUE(item, '$.description') as description,
        JSON_VALUE(item, '$.category') as category,
        JSON_VALUE(item, '$.image') as image_url,
        CAST(JSON_VALUE(item, '$.price') AS FLOAT64) as price,
        CAST(JSON_VALUE(item, '$.rating.rate') AS FLOAT64) as rating_rate,
        CAST(JSON_VALUE(item, '$.rating.count') AS INT64) as rating_count,
        extracted_at,
        run_id

    FROM latest_run,
    UNNEST(JSON_QUERY_ARRAY(data)) as item
)

SELECT * FROM flattened