# Configuration Documentation

This document describes the configuration structure for tables and buckets in the system.

## Tables

Each table entry contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Unique identifier for the table |
| pointInTimeRecovery | boolean | Enables/disables point-in-time recovery |
| description | string | Brief description of the table's purpose |
| enableStream | boolean | (Optional) Enables/disables streaming for the table |
| timeToLiveAttribute | string | (Optional) Specifies the attribute for TTL |
| secondaryIndexes | array of strings | (Optional) List of secondary indexes (not implemented yet) |
| partitionKey | string | (Optional) Specifies the partition key |

### Usage Example

```json
{
  "name": "books",
  "pointInTimeRecovery": true,
  "description": "Books.",
  "enableStream": true,
  "secondaryIndexes": ["appleBookId"]
}
```

## Buckets

Each bucket entry contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Unique identifier for the bucket |
| public | boolean | Determines if the bucket is publicly accessible |
| uploadAssets | boolean | Allows/disallows asset uploads |
| allowedOrigins | array of strings | (Optional) List of allowed origins for CORS |

### Usage Example

```json
{
  "name": "entrepot",
  "public": false,
  "uploadAssets": false,
  "allowedOrigins": [
    "*"
  ]
}
```

## APIs

### Structure

Each API entry contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| type | string | API type: "ws" (WebSocket) or "http" |
| name | string | Unique identifier for the API |
| description | string | Brief description of the API's purpose |
| integrations | object | (WebSocket only) Lambda function integrations |
| allowCredentials | boolean | (HTTP only) Enables/disables credentials |
| cloudfront | string | (HTTP only) Associated CloudFront distribution (not implemented yet) |
| allowOrigins | array of strings | (HTTP only) Allowed CORS origins |
| authorizerFunction | object | (HTTP only) API authorizer configuration |
| key | string | (HTTP only) API key |

### Example (WebSocket API)

```json
{
  "type": "ws",
  "name": "ws_editor",
  "description": "general websocket api for webapp",
  "integrations": {
    "connect": "ws_listener_editor",
    "disconnect": "ws_listener_editor",
    "default": "ws_listener_editor"
  }
}
```

### Example (HTTP API)

```json
{
  "type": "http",
  "name": "editor",
  "description": "atlas media webapp http api",
  "allowCredentials": true,
  "cloudfront": "editor",
  "allowOrigins": [
    "http://localhost:8080",
    "http://atlas-dev-webapp.s3-website-us-east-1.amazonaws.com"
  ],
  "authorizerFunction": {
    "name": "editor_api_authorizer",
    "resultsCacheTtl": 10,
    "identitySource": [
      "$request.header.X-API-KEY",
      "$request.header.X-AUTH-TOKEN"
    ]
  },
  "key": "776f3d9f-c936-4038-b378-42febf2d919b"
}
```

## Lambda Specifications

### Structure

Each Lambda specification contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Unique identifier for the Lambda function |
| description | string | Brief description of the function's purpose |
| tables | object | DynamoDB table access permissions |
| layers | array of objects | Associated Lambda layers |
| apis | array of objects | API integrations |
| buckets | object | (Optional) S3 bucket access permissions |
| activateAuthorizerFunction | boolean | (Optional) Enables/disables authorizer |
| skipAuthorizerFunction | boolean | (Optional) Skips authorizer function |
| eventSources | array of objects | (Optional) Event sources for the function |

### Example

```json
{
  "name": "editor_get_books",
  "description": "Get allowed books",
  "activateAuthorizerFunction": true,
  "tables": {
    "read": [
      "book_distributor",
      "books",
      "general_parameters"
    ],
    "write": []
  },
  "apis": [
    {
      "type": "http",
      "name": "editor",
      "path": "/books",
      "methods": ["GET"]
    },
    {
      "type": "http",
      "name": "editor",
      "path": "/books/{id}",
      "methods": ["GET"]
    }
  ],
  "buckets": {
    "read": ["entrepot"]
  },
  "layers": [
    {
      "name": "awsHelpers"
    }
  ]
}
```

## Notes

- The `enableStream` field is present in most table configurations but not all. Its absence implies the feature is not applicable or disabled by default.
- The `timeToLiveAttribute` is only present in tables that require automatic deletion of items after a certain time.
- `secondaryIndexes` are defined only for tables that require additional access patterns.
- The `partitionKey` is explicitly defined only when it differs from the default.
- `allowedOrigins` in bucket configurations is used to specify CORS settings, with "*" indicating all origins are allowed.
- The `integrations` field in WebSocket APIs specifies Lambda functions for different connection events.
- HTTP APIs can have an `authorizerFunction` for request authorization.
- Lambda functions can have different access permissions for DynamoDB tables and S3 buckets.
- The `activateAuthorizerFunction` and `skipAuthorizerFunction` fields control the use of the authorizer for specific Lambda functions.
- Event sources can be specified for Lambda functions that respond to specific events
