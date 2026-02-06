WITH source AS (
    SELECT * FROM {{ source('fake_store', 'carts_raw_stream') }}
),

parsed AS (
    SELECT
        
        JSON_VALUE(data, '$.id') as cart_id,
        CAST(JSON_VALUE(data, '$.userId') AS INT64) as user_id,
        TIMESTAMP(JSON_VALUE(data, '$.date')) as cart_date,
        JSON_QUERY_ARRAY(data, '$.products') as products_array,
        event_id,
        event_type,
        published_at
    FROM source
),

deduplicated AS (
    SELECT *
    FROM parsed
    QUALIFY ROW_NUMBER() OVER (PARTITION BY cart_id ORDER BY published_at DESC) = 1
)

SELECT * FROM deduplicated
WHERE event_type != 'cart_deleted'