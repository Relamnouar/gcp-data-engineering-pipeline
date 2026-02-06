WITH source AS (
    SELECT * FROM {{ source('fake_store', 'users_raw') }}
),

latest_run AS (
    SELECT * FROM source 
    QUALIFY ROW_NUMBER() OVER (ORDER BY extracted_at DESC) = 1
),

flattened AS (
    SELECT
        
        CAST(JSON_VALUE(item, '$.id') AS INT64) as user_id,
        JSON_VALUE(item, '$.username') as username,
        JSON_VALUE(item, '$.email') as email,
        JSON_VALUE(item, '$.phone') as phone,
        JSON_VALUE(item, '$.name.firstname') as firstname,
        JSON_VALUE(item, '$.name.lastname') as lastname,
        CONCAT(JSON_VALUE(item, '$.name.firstname'), ' ', JSON_VALUE(item, '$.name.lastname')) as full_name,
        JSON_VALUE(item, '$.address.city') as city,
        JSON_VALUE(item, '$.address.street') as street,
        CAST(JSON_VALUE(item, '$.address.number') AS INT64) as street_number,
        JSON_VALUE(item, '$.address.zipcode') as zipcode,
        CAST(JSON_VALUE(item, '$.address.geolocation.lat') AS FLOAT64) as latitude,
        CAST(JSON_VALUE(item, '$.address.geolocation.long') AS FLOAT64) as longitude,
        extracted_at,
        run_id

    FROM latest_run,
    UNNEST(JSON_QUERY_ARRAY(data)) as item
)

SELECT * FROM flattened