# Detections API

This project provides an API for recording and retrieving parking detections.

## 1. Getting Started

### 1.1. Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (a fast Python package installer)

### 1.2. Installation

```bash
uv init detections-api
cd detections-api
uv add fastapi uuid6 uvicorn
```

### 1.3. Running the API

```bash
uv venv
uv run uvicorn main:app --reload
```

The API will start on the default port (e.g., `http://localhost:8000`).

### 1.4. Accessing the API documentation

```bash
open http://127.0.0.1:8000/docs
```

## 2. Detection

Data structure
 - A customer has one or many sites. 
 - A site has one or many zone. 
 - A zone has one or many cameras.

Each detection contains the time of detection (`ts`), the total number of available spaces (`totalSpaces`) covered by this camera and the number of currently occupied spaces (`occupiedSpaces`). The `totalSpaces` is included because it can change over time even if the camera doesn't move.

Considering this, a detection complies to the following:

|property|type|description|
|-|-|-|
|`id`| Optional[str] = None            | unique identifier (UUIDv7)|
|`ts`| Optional[int] = None            | timestamp in ms since Epoch|
|`customerId`| Optional[str] = None    | curtomer unique identifier (UUIDv7). Must match header if provided|
|`siteId`| str                         | site unique identifier (UUIDv7)|
|`zoneId`| str                         | zone unique identifier (UUIDv7)|
|`cameraId`| str                       | camera unique identifier (UUIDv7)|
|`totalSpaces`| int = 0                | total parking spaces  |
|`occupiedSpaces| int = 0              | occupied parking spaces|


If `id` isn't provided, one will be generated.

If `ts` isn't provided, one will be generated as of the current time.

if `customerId` is provided, it must exactly match the one provided in the header.

All `id`s, are UUIDv7.

## 3. Project Structure

```
.
├── main.py
├── requirements.txt
└── README.md
```

## 4. Usage

Refer to the [API documentation](http://127.0.0.1:8000/docs) or inspect `main.py` for all available endpoints. 

Here are some usage examples.

### 4.1. POST /detections

```curl
curl --location 'http://127.0.0.1:8000/detections' \
--header 'x-customer-id: 019949CE-8A59-7016-8498-7DE5E32D7B9D' \
--header 'x-api-key: 019949D0-BDE6-724C-9853-BC274CF48337' \
--header 'x-secret-key: 019949D1-0B11-7E7C-B078-751B6687FC9B' \
--header 'Content-Type: application/json' \
--data '{
	"ts": 1757881561805,
	"siteId": "019949E8-2178-70D2-9E9E-D2954D2AECB7",
	"zoneId": "019949E8-4319-754E-AA3F-0F1E89C6D2DD",
	"cameraId": "019949E8-602D-7C07-BDBC-CD897BA46F92",
	"totalSpaces": 50,
    "occupiedSpaces": 10
}'
```

returns

```json
{
    "id": "019949E7-CDE5-71FE-87EC-29DCAC160FA2",
    "ts": 1757881561805,
    "customerId": "019949CE-8A59-7016-8498-7DE5E32D7B9D",
    "siteId": "019949E8-2178-70D2-9E9E-D2954D2AECB7",
    "zoneId": "019949E8-4319-754E-AA3F-0F1E89C6D2DD",
    "cameraId": "019949E8-602D-7C07-BDBC-CD897BA46F92",
    "totalSpaces": 50,
    "occupiedSpaces": 10
}
```

Note the `id` and `customerId` have been added.


### 4.2. GET /detections

```curl
curl --location 'http://127.0.0.1:8000/detections' \
--header 'X-CUSTOMER-ID: 019949CE-8A59-7016-8498-7DE5E32D7B9D' \
--header 'x-api-key: 019949D0-BDE6-724C-9853-BC274CF48337' \
--header 'x-secret-key: 019949D1-0B11-7E7C-B078-751B6687FC9B' \
--data ''
```

returns all detection of customer.

### 4.3. GET /detections of a camera

Let's only ave the detections for cameras with id 019949E8-602D-7C07-BDBC-CD897BA46F92 and 01994DE4-2556-71BD-9878-6EB7B6490247:

```curl
curl --location 'http://127.0.0.1:8000/detections?cameraId=019949E8-602D-7C07-BDBC-CD897BA46F92,01994DE4-2556-71BD-9878-6EB7B6490247' \
--header 'X-CUSTOMER-ID: 019949CE-8A59-7016-8498-7DE5E32D7B9D' \
--header 'x-api-key: 019949D0-BDE6-724C-9853-BC274CF48337' \
--header 'x-secret-key: 019949D1-0B11-7E7C-B078-751B6687FC9B' \
--data ''
```

The same filtering can be applied for detection `id`, `siteId` and `zoneId`. Yhe request can specify one of many comma-separated ids.

### 4.4. GET /detections of a window, binned

```curl
curl --location 'http://127.0.0.1:8000/detections?start=1000&end=86400000&bin=3600000' \
--header 'x-customer-id: 019949CE-8A59-7016-8498-7DE5E32D7B9D' \
--header 'x-api-key: 019949D0-BDE6-724C-9853-BC274CF48337' \
--header 'x-secret-key: 019949D1-0B11-7E7C-B078-751B6687FC9B'
```

returns

```json
[
    {
        "ts": 1800000,
        "customerId": "019949CE-8A59-7016-8498-7DE5E32D7B9D",
        "siteId": "019949E8-2178-70D2-9E9E-D2954D2AECB7",
        "zoneId": "019949E8-4319-754E-AA3F-0F1E89C6D2DD",
        "cameraId": "019949E8-602D-7C07-BDBC-CD897BA46F92",
        "min_total_spaces": 50,
        "min_occupied_spaces": 20,
        "mean_total_spaces": 50,
        "mean_occupied_spaces": 25,
        "max_total_spaces": 50,
        "max_occupied_spaces": 30,
        "number_of_detections": 2,
        "detectionIds": [
            "01994de8-f1eb-7281-b40b-aa6b9e404feb",
            "01994de8-f1ec-7147-b9b4-10d275f033fd"
        ]
    },
    {
        "ts": 5400000,
        "customerId": "019949CE-8A59-7016-8498-7DE5E32D7B9D",
        "siteId": "019949E8-2178-70D2-9E9E-D2954D2AECB7",
        "zoneId": "019949E8-4319-754E-AA3F-0F1E89C6D2DD",
        "cameraId": "019949E8-602D-7C07-BDBC-CD897BA46F92",
        "min_total_spaces": 50,
        "min_occupied_spaces": 30,
        "mean_total_spaces": 50,
        "mean_occupied_spaces": 35,
        "max_total_spaces": 50,
        "max_occupied_spaces": 40,
        "number_of_detections": 2,
        "detectionIds": [
            "01994de8-f1ed-7403-8c2d-809a55385b1e",
            "01994de8-f1ee-71a2-969d-288f7d5932c8"
        ]
    }
]
```
