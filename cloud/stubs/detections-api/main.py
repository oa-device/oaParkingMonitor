#!/usr/bin/env python3

# This is a stub implementation of the Detections API.
# It supports creating and querying detections with filtering and binning.
# It uses FastAPI and Pydantic for request handling and data validation.

#--- Imports ---
from collections import defaultdict
from fastapi import FastAPI, Header, HTTPException, Query, Depends, Body # pyright: ignore[reportMissingImports]
from pydantic import BaseModel # pyright: ignore[reportMissingImports]
from statistics import mean
from typing import Optional, List, Union
from uuid6 import UUID, uuid7 # pyright: ignore[reportMissingImports]
import time


#--- FastAPI app initialization ---
app = FastAPI(title="Detections API")


# --- Security constants ---
EXPECTED_CUSTOMER_ID = "019949CE-8A59-7016-8498-7DE5E32D7B9D"
EXPECTED_API_KEY = "019949D0-BDE6-724C-9853-BC274CF48337"
EXPECTED_SECRET_KEY = "019949D1-0B11-7E7C-B078-751B6687FC9B"


# --- Data model ---
class Detection(BaseModel):
    id: Optional[str] = None            # UUIDv7
    ts: Optional[int] = None            # timestamp in ms since Epoch
    customerId: Optional[str] = None    # must match header if provided
    siteId: str                         # site identifier
    zoneId: str                         # zone identifier
    cameraId: str                       # camera identifier
    totalSpaces: int = 0                # total parking spaces  
    occupiedSpaces: int = 0             # occupied parking spaces
class BinnedDetection(BaseModel):
    ts: Optional[int] = None            # timestamp in ms since Epoch
    customerId: Optional[str] = None    # must match header if provided
    siteId: str                         # site identifier
    zoneId: str                         # zone identifier
    cameraId: str                       # camera identifier
    minTotalSpaces: int                 # minimum total spaces
    minOccupiedSpaces: int              # minimum occupied spaces
    meanTotalSpaces: int                # mean total spaces
    meanOccupiedSpaces: int             # mean occupied spaces
    maxTotalSpaces: int                 # maximum total spaces
    maxOccupiedSpaces: int              # maximum occupied spaces
    numberOfDetections: int             # number of detections in the bin
    detectionIds: List[str]             # list of detection ids in the bin

# In-memory storage for detections
detections: List[Detection] = []

# --- Header validation ---

# Dependency to validate headers
def validate_headers(
    x_customer_id: str = Header(..., alias="x-customer-id"),
    x_api_key: str = Header(..., alias="x-api-key"),
    x_secret_key: str = Header(..., alias="x-secret-key"),
):
    # Validate headers against expected values
    if (
        x_customer_id != EXPECTED_CUSTOMER_ID
        or x_api_key != EXPECTED_API_KEY
        or x_secret_key != EXPECTED_SECRET_KEY
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_customer_id

#--- API Endpoints ---

@app.post("/detections", response_model=Union[Detection, List[Detection]])
# Create one or more detections
def create_detections(
    body: Union[Detection, List[Detection]] = Body(...),
    customer_id: str = Depends(validate_headers)
):
    # Normalize into a list
    detections_list = body if isinstance(body, list) else [body]
    created: List[Detection] = []

    # Process each detection
    for detection in detections_list:
        # Enforce customer consistency
        if detection.customerId and detection.customerId != customer_id:
            raise HTTPException(status_code=403, detail="Customer mismatch")
        detection.customerId = customer_id  

        # Auto-generate UUIDv7 if not provided
        if detection.id is None:
            detection.id = str(uuid7())
        else:
            try:
                # Validate UUIDv7 format
                parsed = UUID(detection.id)
                if parsed.version != 7:
                    raise ValueError("Not a UUIDv7")
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="detection.id must be a valid UUIDv7"
                )

        # Make sure th uuid is unique
        if any(d.id == detection.id for d in detections):
            raise HTTPException(status_code=409, detail="Duplicate detection.id")

        # Ensure timestamp: is not provided, add now in ms
        if detection.ts is None:
            detection.ts = int(time.time() * 1000)

        detections.append(detection)
        created.append(detection)

    # Return a single object if a single was sent, else a list
    return created if isinstance(body, list) else created[0]


@app.get("/detections", response_model=List[BinnedDetection])
# Query parameters for filtering and binning
def get_detections(
    customerId: str         = Depends(validate_headers),
    id: Optional[str]       = Query(None, description="id(s) of the detection"),
    siteId: Optional[str]   = Query(None, description="id(s) of the site"),
    zoneId: Optional[str]   = Query(None, description="id(s) of the zone"),
    cameraId: Optional[str] = Query(None, description="id(s) of the camera"),
    start: Optional[int]    = Query(None, description="first ts in ms since Epoch"),
    end: Optional[int]      = Query(None, description="last ts in ms since Epoch"),
    bin: Optional[int]      = Query(None, description="bin size in ms"),
):
    # ---- FILTERING ----

    # Start with all observations for this customer
    results = [d for d in detections if d.customerId == customerId]
    if id:
        results = [d for d in results if d.id == id]

    # Support comma-separated lists for siteId, zoneId, cameraId
    if siteId:
        site_ids = [cid.strip() for cid in siteId.split(",")]
        results = [d for d in results if d.siteId in site_ids]
    if zoneId:
        zone_ids = [cid.strip() for cid in zoneId.split(",")]
        results = [d for d in results if d.zoneId in zone_ids]
    if cameraId:
        camera_ids = [cid.strip() for cid in cameraId.split(",")]
        results = [d for d in results if d.cameraId in camera_ids]

    # Filter by time range
    if start is not None:
        results = [d for d in results if d.ts >= start]
    if end is not None:
        results = [d for d in results if d.ts <= end]

    # ---- BINNING ----
    if bin:
        buckets = defaultdict(list)
        for d in results:
            # Determine the bucket index
            bucket_index = d.ts // bin
            buckets[bucket_index].append(d)

        binned_results = []
        for bucket_index, detections_list in buckets.items():
            ts_start = bucket_index * bin
            ts_mid   = ts_start + bin // 2. # Midpoint of the bin

            total_spaces    = [d.totalSpaces for d in detections_list]
            occupied_spaces = [d.occupiedSpaces for d in detections_list]

            mean_total_spaces    = mean(total_spaces)
            mean_occupied_spaces = mean(occupied_spaces)
            min_total_spaces     = min(total_spaces)
            min_occupied_spaces  = min(occupied_spaces)
            max_total_spaces     = max(total_spaces)
            max_occupied_spaces  = max(occupied_spaces)

            number_of_detections = len(total_spaces)
            detection_ids = [d.id for d in detections_list]

            binned_results.append(BinnedDetection(
                ts                  = ts_mid,
                customerId          = customerId,
                siteId              = detections_list[0].siteId,
                zoneId              = detections_list[0].zoneId,
                cameraId            = detections_list[0].cameraId,
                minTotalSpaces      = min_total_spaces,
                minOccupiedSpaces   = min_occupied_spaces,
                meanTotalSpaces     = mean_total_spaces,
                meanOccupiedSpaces  = mean_occupied_spaces,
                maxTotalSpaces      = max_total_spaces,
                maxOccupiedSpaces   = max_occupied_spaces,
                numberOfDetections  = number_of_detections,
                detectionIds        = detection_ids,
            ))

        results = binned_results

    return results
# eof