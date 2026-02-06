WITH stg_users AS (
    SELECT * FROM {{ ref('stg_users') }}
)

SELECT
    user_id,
    username,
    full_name,
    email,
    phone,
    city,
    street,
    street_number,
    zipcode,
    latitude,
    longitude,
    ST_GEOGPOINT(longitude, latitude) as location_point

FROM stg_users