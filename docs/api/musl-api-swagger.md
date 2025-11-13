# MUSL Game Service API - Swagger Documentation

## API Information
- **Title:** MUSL Game Service API
- **Version:** 1.0.0
- **Base URL:** https://api.musl.com
- **Generator:** NSwag v14.6.0.0

## Security
All endpoints require API key authentication via `x-api-key` header.

---

## Endpoints

### 1. Grand Prize API

#### GET /v3/grandprize
Returns Grand Prize Amounts

**Parameters:**
- `DrawId` (query, guid): The unique drawing, overrides DrawDate and GameCode if supplied
- `DrawDate` (query, date): The date of the drawing in the United States
- `ExternalDrawId` (query, string): External identifier for FastPlay Games
- `GameCode` (query, string): Game Code for which you want data for (default: 'powerball')

**Responses:**
- 200: Grand Prize information
- 400, 401, 404, 429, 500, 503: Error responses

#### GET /v3/grandprize.{format}
Same as above with format parameter in path

---

### 2. Winning Numbers API

#### GET /v3/numbers
Returns Winning Numbers

**Parameters:**
- `DrawId` (query, guid): The unique drawing, overrides DrawDate and GameCode if supplied
- `DrawDate` (query, date): The date of the drawing in the United States
- `ExternalDrawId` (query, string): External identifier for FastPlay Games
- `GameCode` (query, string): Game Code for which you want data for (default: 'powerball')

**Responses:**
- 200: Drawn Numbers information
- 400, 401, 404, 429, 500, 503: Error responses

#### GET /v3/numbers.{format}
Same as above with format parameter in path

---

### 3. Winning Tiers API

#### GET /v3/winners
Returns Winning Tiers

**Parameters:**
- `OrganizationCode` (query, string): Filter by organization or state. i.e. IA for Iowa (default: 'ALL')
- `DrawId` (query, guid): The unique drawing, overrides DrawDate and GameCode if supplied
- `DrawDate` (query, date): The date of the drawing in the United States
- `ExternalDrawId` (query, string): External identifier for FastPlay Games
- `GameCode` (query, string): Game Code for which you want data for (default: 'powerball')

**Responses:**
- 200: Winning tier information
- 400, 401, 404, 429, 500, 503: Error responses

#### GET /v3/winners.{format}
Same as above with format parameter in path

---

### 4. Draw Report API

#### GET /v3/drawreport
Returns Grand Prize, Numbers, and Winning Tiers

**Parameters:**
- `OrganizationCode` (query, string): Filter by organization or state. i.e. IA for Iowa (default: 'ALL')
- `DrawId` (query, guid): The unique drawing, overrides DrawDate and GameCode if supplied
- `DrawDate` (query, date): The date of the drawing in the United States
- `ExternalDrawId` (query, string): External identifier for FastPlay Games
- `GameCode` (query, string): Game Code for which you want data for (default: 'powerball')

**Responses:**
- 200: Draw Report
- 400, 401, 404, 429, 500, 503: Error responses

#### GET /v3/drawreport.{format}
Same as above with format parameter in path

---

### 5. Games API

#### GET /v3/games
Returns Games

**Parameters:** None

**Responses:**
- 200: Games information
- 400, 401, 404, 429, 500, 503: Error responses

#### GET /v3/games.{format}
Same as above with format parameter in path

---

## Data Models

### GrandPrizeResponseModel
Extends BaseResponseModel with:
- `grandPrize` (GrandPrizeModel, nullable)

### GrandPrizeModel
- `advertized` (decimal): The advertized prize value
- `annuity` (decimal, nullable): The annuitized prize value if game supports annuity payout
- `cash` (decimal): The cash prize value
- `nextAnnuity` (decimal, nullable): The next annuitized prize (not official until status = 'complete')
- `nextCash` (decimal): The next cash value (not official until status = 'complete')
- `prizeText` (string): English friendly prize display (e.g., '$1.100 Billion')
- `cashPrizeText` (string): English friendly cash prize display (e.g., '$550.2 Million')
- `prizeCombined` (string): Combined prize display (e.g., '$1.100 Billion ($550.2 Million Cash Value)')
- `nextPrizeText` (string): Next prize display (e.g., '$1.35 Billion')
- `nextCashPrizeText` (string): Next cash prize display (e.g., '$659.5 Million')
- `nextPrizeCombined` (string): Next combined prize display

### BaseResponseModel
- `drawId` (guid, required): The unique ID for the drawing
- `game` (GameInfoModel, required): The game information
- `statusCode` (string, required): Status of the drawing (when 'complete', next Grand Prize is valid)
- `drawDate` (date): The draw date in YYYY-MM-DD format
- `drawDateUtc` (datetime): Draw date and estimated time in UTC
- `externalDrawId` (string, nullable): External draw identifier
- `previousDrawing` (DrawInfoModel, nullable): The previous drawing
- `nextDrawing` (DrawInfoModel, nullable): The next drawing

### GameInfoModel
- `code` (string, required): Unique code for the drawing
- `name` (string): The name of the Game

### DrawInfoModel
- `drawId` (guid, required): The unique id for the drawing
- `drawDate` (date): The draw date in YYYY-MM-DD format
- `drawDateUtc` (datetime): Draw date and estimated time in UTC
- `externalDrawId` (string, nullable): External draw identifier

### NumberResponseModel
Extends BaseResponseModel with:
- `numbers` (array of NumberModel, nullable): Numbers Drawn

### NumberModel
- `itemCode` (string, required): The item code for which this number is drawn
- `ruleCode` (string, required): The rule code for which this number is drawn
- `value` (string): The number drawn
- `orderDrawn` (integer): The order in which the number was drawn for the rule

### WinnerResponseModel
Extends BaseResponseModel with:
- `winners` (WinnerModel, nullable)

### WinnerModel
- `organizationCode` (string, required)
- `topTiers` (array of TopWinnerTierModel, nullable)
- `tiers` (array of WinnerTierModel, nullable)

### TopWinnerTierModel
Extends WinnerTierModel with:
- `prizeDescription` (string)
- `summaryWinnerText` (string)
- `organizationString` (string)
- `organizationCodes` (array of string)
- `organizations` (array of OrganizationWinnerCountModel)

### OrganizationWinnerCountModel
- `organizationCode` (string)
- `count` (integer)

### WinnerTierModel
- `itemCode` (string, required)
- `tierCode` (string, required)
- `count` (integer)

### DrawReportResponseModel
Extends BaseResponseModel with:
- `grandPrize` (GrandPrizeModel, nullable): Contains the Grand Prize values
- `numbers` (array of NumberModel, nullable): Contains the winning number values
- `winners` (WinnerModel, nullable): Contains the winning tiers values

### GameResponseModel
- `games` (array of GameModel, nullable): List of active and inactive games

### GameModel
- `code` (string, required): Unique code representing the game
- `name` (string): The name of the game
- `isActive` (boolean): Indicates the game is still active
- `organizations` (array of OrganizationModel, nullable): Participating organizations
- `components` (array of ComponentModel, nullable): Individual components of the game

### OrganizationModel
- `organizationCode` (string, required): Unique code (2 digit US State/Territory abbreviation)
- `name` (string): Name of the lottery

### ComponentModel
- `itemCode` (string, required): The unique item code for the component
- `name` (string): The name of the component
- `drawDays` (array of string, nullable): Days of the week the component is drawn
- `rules` (array of RuleModel, nullable): Rules that make up the component
- `tiers` (array of TierModel, nullable): Different winning tiers that pay out prizes

### RuleModel
- `ruleCode` (string, required): Unique code for the rule
- `name` (string): The name of the rule
- `quantity` (integer): Number of numbers or balls drawn
- `startNumber` (integer): Minimum value or ball number
- `endNumber` (integer): Maximum value or ball number

### TierModel
- `tierCode` (string, required): Unique identifier for the tier
- `name` (string): The name of the Tier
- `prizeDescription` (string): Description of the prize
- `prize` (decimal, nullable): US Dollar amount the prize pays

### ProblemDetails
Standard error response model with:
- `type` (string)
- `title` (string)
- `status` (integer)
- `detail` (string)
- `instance` (string)

---

## Complete JSON

```json
{
  "x-generator": "NSwag v14.6.0.0 (NJsonSchema v11.5.0.0 (Newtonsoft.Json v13.0.0.0))",
  "openapi": "3.0.0",
  "info": {
    "title": "MUSL Game Service API",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "https://api.musl.com"
    }
  ],
  "paths": {
    "/v3/grandprize": {
      "get": {
        "tags": [
          "Get Grand Prize"
        ],
        "summary": "Returns Grand Prize Amounts",
        "operationId": "gameServiceGetGrandPrize",
        "parameters": [
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          }
        ],
        "responses": {
          "200": {
            "description": "Grand Prize information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/GrandPrizeResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/grandprize.{format}": {
      "get": {
        "tags": [
          "Get Grand Prize"
        ],
        "summary": "Returns Grand Prize Amounts",
        "operationId": "gameServiceGetGrandPrize2",
        "parameters": [
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          },
          {
            "name": "format",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string"
            },
            "x-position": 5
          }
        ],
        "responses": {
          "200": {
            "description": "Grand Prize information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/GrandPrizeResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/numbers": {
      "get": {
        "tags": [
          "Get Winning Numbers"
        ],
        "summary": "Returns Winning Numbers",
        "operationId": "gameServiceNumbers",
        "parameters": [
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          }
        ],
        "responses": {
          "200": {
            "description": "Drawn Numbers information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/NumberResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/numbers.{format}": {
      "get": {
        "tags": [
          "Get Winning Numbers"
        ],
        "summary": "Returns Winning Numbers",
        "operationId": "gameServiceNumbers2",
        "parameters": [
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          },
          {
            "name": "format",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string"
            },
            "x-position": 5
          }
        ],
        "responses": {
          "200": {
            "description": "Drawn Numbers information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/NumberResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/winners": {
      "get": {
        "tags": [
          "Get Winning Tiers"
        ],
        "summary": "Returns Winning Tiers",
        "operationId": "gameServiceWinners",
        "parameters": [
          {
            "name": "OrganizationCode",
            "in": "query",
            "description": "Filter by organization or state. i.e. IA for Iowa (default: 'ALL')\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 5
          }
        ],
        "responses": {
          "200": {
            "description": "Winning tier information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/WinnerResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/winners.{format}": {
      "get": {
        "tags": [
          "Get Winning Tiers"
        ],
        "summary": "Returns Winning Tiers",
        "operationId": "gameServiceWinners2",
        "parameters": [
          {
            "name": "OrganizationCode",
            "in": "query",
            "description": "Filter by organization or state. i.e. IA for Iowa (default: 'ALL')\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 5
          },
          {
            "name": "format",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string"
            },
            "x-position": 6
          }
        ],
        "responses": {
          "200": {
            "description": "Winning tier information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/WinnerResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/drawreport": {
      "get": {
        "tags": [
          "Get Draw Report"
        ],
        "summary": "Returns Grand Prize, Numbers, and Winning Tiers",
        "operationId": "gameServiceDrawReport",
        "parameters": [
          {
            "name": "OrganizationCode",
            "in": "query",
            "description": "Filter by organization or state. i.e. IA for Iowa (default: 'ALL')\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 5
          }
        ],
        "responses": {
          "200": {
            "description": "Draw Report",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/DrawReportResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/drawreport.{format}": {
      "get": {
        "tags": [
          "Get Draw Report"
        ],
        "summary": "Returns Grand Prize, Numbers, and Winning Tiers",
        "operationId": "gameServiceDrawReport2",
        "parameters": [
          {
            "name": "OrganizationCode",
            "in": "query",
            "description": "Filter by organization or state. i.e. IA for Iowa (default: 'ALL')\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 1
          },
          {
            "name": "DrawId",
            "in": "query",
            "description": "The unique drawing, if supplied this overrides DrawDate and GameCode\n            ",
            "schema": {
              "type": "string",
              "format": "guid",
              "nullable": true
            },
            "x-position": 2
          },
          {
            "name": "DrawDate",
            "in": "query",
            "description": "The date of the drawing in the United States\n            ",
            "schema": {
              "type": "string",
              "format": "full-date",
              "nullable": true
            },
            "x-position": 3
          },
          {
            "name": "ExternalDrawId",
            "in": "query",
            "description": "External identifier for FastPlay Games\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 4
          },
          {
            "name": "GameCode",
            "in": "query",
            "description": "Game Code for which you want data for (default: 'powerball').\n            ",
            "schema": {
              "type": "string",
              "nullable": true
            },
            "x-position": 5
          },
          {
            "name": "format",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string"
            },
            "x-position": 6
          }
        ],
        "responses": {
          "200": {
            "description": "Draw Report",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/DrawReportResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/games": {
      "get": {
        "tags": [
          "Get Games"
        ],
        "summary": "Returns Games",
        "operationId": "gameServiceGames",
        "responses": {
          "200": {
            "description": "Games information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/GameResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    },
    "/v3/games.{format}": {
      "get": {
        "tags": [
          "Get Games"
        ],
        "summary": "Returns Games",
        "operationId": "gameServiceGames2",
        "parameters": [
          {
            "name": "format",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string"
            },
            "x-position": 1
          }
        ],
        "responses": {
          "200": {
            "description": "Games information",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/GameResponseModel"
                }
              }
            }
          },
          "400": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "401": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "404": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "429": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "500": {
            "description": "",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ProblemDetails"
                }
              }
            }
          },
          "503": {
            "description": ""
          }
        },
        "security": [
          {
            "x-api-key": []
          }
        ]
      }
    }
  },
  "components": {
    "schemas": {
      "GrandPrizeResponseModel": {
        "allOf": [
          {
            "$ref": "#/components/schemas/BaseResponseModel"
          },
          {
            "type": "object",
            "description": "Represents the grand prize API response model\n            ",
            "additionalProperties": false,
            "properties": {
              "grandPrize": {
                "nullable": true,
                "oneOf": [
                  {
                    "$ref": "#/components/schemas/GrandPrizeModel"
                  }
                ]
              }
            }
          }
        ]
      },
      "GrandPrizeModel": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "advertized": {
            "type": "number",
            "description": "The advertized prize value\n            ",
            "format": "decimal"
          },
          "annuity": {
            "type": "number",
            "description": "The annuitized prize value if game supports annuity payout\n            ",
            "format": "decimal",
            "nullable": true
          },
          "cash": {
            "type": "number",
            "description": "The cash prize value\n            ",
            "format": "decimal"
          },
          "nextAnnuity": {
            "type": "number",
            "description": "The next annuitized prize if game supports annuity payout, this value is not official until\n equals 'complete'\n            ",
            "format": "decimal",
            "nullable": true
          },
          "nextCash": {
            "type": "number",
            "description": "The next cash value, this value is not official until  equals\n'complete'\n            ",
            "format": "decimal"
          },
          "prizeText": {
            "type": "string",
            "description": "English friendly prize display of current prize i.e '$1.100 Billion'",
            "nullable": true
          },
          "cashPrizeText": {
            "type": "string",
            "description": "English friendly prize display of current cash prize i.e '$550.2 Million'",
            "nullable": true
          },
          "prizeCombined": {
            "type": "string",
            "description": "English friendly prize display of current prize with cash i.e '$1.100 Billion ($550.2 Million Cash Value)'",
            "nullable": true
          },
          "nextPrizeText": {
            "type": "string",
            "description": "English friendly prize display of next prize i.e '$1.35 Billion'",
            "nullable": true
          },
          "nextCashPrizeText": {
            "type": "string",
            "description": "English friendly prize display of next cash prize i.e '$659.5 Million'",
            "nullable": true
          },
          "nextPrizeCombined": {
            "type": "string",
            "description": "English friendly prize display of next prize with cash i.e '$1.35 Billion ($659.5 Million Cash Value)'",
            "nullable": true
          }
        }
      },
      "BaseResponseModel": {
        "type": "object",
        "x-abstract": true,
        "additionalProperties": false,
        "required": [
          "drawId",
          "game",
          "statusCode"
        ],
        "properties": {
          "drawId": {
            "type": "string",
            "description": "The unique ID for the drawing\n            ",
            "format": "guid",
            "minLength": 1
          },
          "game": {
            "description": "The game information\n            ",
            "oneOf": [
              {
                "$ref": "#/components/schemas/GameInfoModel"
              }
            ]
          },
          "statusCode": {
            "type": "string",
            "description": "Status of the drawing. When value is complete the next Grand Prize is valid.\n            ",
            "minLength": 1
          },
          "drawDate": {
            "type": "string",
            "description": "The draw date in YYYY-MM-DD format",
            "format": "full-date"
          },
          "drawDateUtc": {
            "type": "string",
            "description": "Draw date and estimated time for which the numbers will be drawn in UTC\n            ",
            "format": "date-time"
          },
          "externalDrawId": {
            "type": "string",
            "description": "External draw identifier for Game.\n            ",
            "nullable": true
          },
          "previousDrawing": {
            "description": "The previous drawing\n            ",
            "nullable": true,
            "oneOf": [
              {
                "$ref": "#/components/schemas/DrawInfoModel"
              }
            ]
          },
          "nextDrawing": {
            "description": "The next drawing\n            ",
            "nullable": true,
            "oneOf": [
              {
                "$ref": "#/components/schemas/DrawInfoModel"
              }
            ]
          }
        }
      },
      "GameInfoModel": {
        "type": "object",
        "description": "The game information\n            ",
        "additionalProperties": false,
        "required": [
          "code"
        ],
        "properties": {
          "code": {
            "type": "string",
            "description": "Unique code for the drawing.  See Games API for valid values\n            ",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "description": "The name of the Game\n            ",
            "nullable": true
          }
        }
      },
      "DrawInfoModel": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "drawId"
        ],
        "properties": {
          "drawId": {
            "type": "string",
            "description": "The unique id for the drawing",
            "format": "guid",
            "minLength": 1
          },
          "drawDate": {
            "type": "string",
            "description": "The draw date in YYYY-MM-DD format",
            "format": "full-date"
          },
          "drawDateUtc": {
            "type": "string",
            "description": "Draw date and estimated time for which the numbers will be drawn in UTC\n            ",
            "format": "date-time"
          },
          "externalDrawId": {
            "type": "string",
            "description": "External draw identifier for Game.\n            ",
            "nullable": true
          }
        }
      },
      "ProblemDetails": {
        "type": "object",
        "additionalProperties": {
          "nullable": true
        },
        "properties": {
          "type": {
            "type": "string",
            "nullable": true
          },
          "title": {
            "type": "string",
            "nullable": true
          },
          "status": {
            "type": "integer",
            "format": "int32",
            "nullable": true
          },
          "detail": {
            "type": "string",
            "nullable": true
          },
          "instance": {
            "type": "string",
            "nullable": true
          }
        }
      },
      "NumberResponseModel": {
        "allOf": [
          {
            "$ref": "#/components/schemas/BaseResponseModel"
          },
          {
            "type": "object",
            "description": "Represents the numbers API response model\n            ",
            "additionalProperties": false,
            "properties": {
              "numbers": {
                "type": "array",
                "description": "Numbers Drawn\n            ",
                "nullable": true,
                "items": {
                  "$ref": "#/components/schemas/NumberModel"
                }
              }
            }
          }
        ]
      },
      "NumberModel": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "itemCode",
          "ruleCode"
        ],
        "properties": {
          "itemCode": {
            "type": "string",
            "description": "The item code for which this number is drawn\n            ",
            "minLength": 1
          },
          "ruleCode": {
            "type": "string",
            "description": "The rule code for which this number is drawn\n            ",
            "minLength": 1
          },
          "value": {
            "type": "string",
            "description": "The number drawn\n            ",
            "nullable": true
          },
          "orderDrawn": {
            "type": "integer",
            "description": "Represents the order in which the number was drawn for the rule\n            ",
            "format": "int32"
          }
        }
      },
      "WinnerResponseModel": {
        "allOf": [
          {
            "$ref": "#/components/schemas/BaseResponseModel"
          },
          {
            "type": "object",
            "description": "Represents the winners API response model\n            ",
            "additionalProperties": false,
            "properties": {
              "winners": {
                "nullable": true,
                "oneOf": [
                  {
                    "$ref": "#/components/schemas/WinnerModel"
                  }
                ]
              }
            }
          }
        ]
      },
      "WinnerModel": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "organizationCode"
        ],
        "properties": {
          "organizationCode": {
            "type": "string",
            "minLength": 1
          },
          "topTiers": {
            "type": "array",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/TopWinnerTierModel"
            }
          },
          "tiers": {
            "type": "array",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/WinnerTierModel"
            }
          }
        }
      },
      "TopWinnerTierModel": {
        "allOf": [
          {
            "$ref": "#/components/schemas/WinnerTierModel"
          },
          {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "prizeDescription": {
                "type": "string",
                "nullable": true
              },
              "summaryWinnerText": {
                "type": "string",
                "nullable": true
              },
              "organizationString": {
                "type": "string",
                "nullable": true
              },
              "organizationCodes": {
                "type": "array",
                "nullable": true,
                "items": {
                  "type": "string"
                }
              },
              "organizations": {
                "type": "array",
                "nullable": true,
                "items": {
                  "$ref": "#/components/schemas/OrganizationWinnerCountModel"
                }
              }
            }
          }
        ]
      },
      "OrganizationWinnerCountModel": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "organizationCode": {
            "type": "string",
            "nullable": true
          },
          "count": {
            "type": "integer",
            "format": "int32"
          }
        }
      },
      "WinnerTierModel": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "itemCode",
          "tierCode"
        ],
        "properties": {
          "itemCode": {
            "type": "string",
            "minLength": 1
          },
          "tierCode": {
            "type": "string",
            "minLength": 1
          },
          "count": {
            "type": "integer",
            "format": "int32"
          }
        }
      },
      "DrawReportResponseModel": {
        "allOf": [
          {
            "$ref": "#/components/schemas/BaseResponseModel"
          },
          {
            "type": "object",
            "description": "Represents the draw report API response model\n            ",
            "additionalProperties": false,
            "properties": {
              "grandPrize": {
                "description": "Contains the Grand Prize values\n            ",
                "nullable": true,
                "oneOf": [
                  {
                    "$ref": "#/components/schemas/GrandPrizeModel"
                  }
                ]
              },
              "numbers": {
                "type": "array",
                "description": "Contains the winning number values\n            ",
                "nullable": true,
                "items": {
                  "$ref": "#/components/schemas/NumberModel"
                }
              },
              "winners": {
                "description": "Contains the winning tiers values\n            ",
                "nullable": true,
                "oneOf": [
                  {
                    "$ref": "#/components/schemas/WinnerModel"
                  }
                ]
              }
            }
          }
        ]
      },
      "GameResponseModel": {
        "type": "object",
        "description": "Represents the games API response model\n            ",
        "additionalProperties": false,
        "properties": {
          "games": {
            "type": "array",
            "description": "List of active and inactive games for which data is available",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/GameModel"
            }
          }
        }
      },
      "GameModel": {
        "type": "object",
        "description": "The container for an individual game\n            ",
        "additionalProperties": false,
        "required": [
          "code"
        ],
        "properties": {
          "code": {
            "type": "string",
            "description": "Unique code representing the game\n            ",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "description": "The name of the game\n            ",
            "nullable": true
          },
          "isActive": {
            "type": "boolean",
            "description": "Indicates the game is still active\n            "
          },
          "organizations": {
            "type": "array",
            "description": "Contains all the participating organizations for the game\n            ",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/OrganizationModel"
            }
          },
          "components": {
            "type": "array",
            "description": "Contains individual components of the game\n            ",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/ComponentModel"
            }
          }
        }
      },
      "OrganizationModel": {
        "type": "object",
        "description": "The Organization information\n            ",
        "additionalProperties": false,
        "required": [
          "organizationCode"
        ],
        "properties": {
          "organizationCode": {
            "type": "string",
            "description": "The unique code for the organization, currently the 2 digit abbreviation for US States and Territories\n            ",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "description": "Name of the lottery\n            ",
            "nullable": true
          }
        }
      },
      "ComponentModel": {
        "type": "object",
        "description": "Represents a unique component to a game\n            ",
        "additionalProperties": false,
        "required": [
          "itemCode"
        ],
        "properties": {
          "itemCode": {
            "type": "string",
            "description": "The unique item code for the component\n            ",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "description": "The name of the component\n            ",
            "nullable": true
          },
          "drawDays": {
            "type": "array",
            "description": "The days of the week that the component is drawn\n            ",
            "nullable": true,
            "items": {
              "type": "string"
            }
          },
          "rules": {
            "type": "array",
            "description": "The rules that make up the component\n            ",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/RuleModel"
            }
          },
          "tiers": {
            "type": "array",
            "description": "The different winning tiers that pay out prizes\n            ",
            "nullable": true,
            "items": {
              "$ref": "#/components/schemas/TierModel"
            }
          }
        }
      },
      "RuleModel": {
        "type": "object",
        "description": "Represents a rule for a component\n            ",
        "additionalProperties": false,
        "required": [
          "ruleCode"
        ],
        "properties": {
          "ruleCode": {
            "type": "string",
            "description": "Unique code for the rule\n            ",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "description": "The name of the rule\n            ",
            "nullable": true
          },
          "quantity": {
            "type": "integer",
            "description": "Number of numbers or balls drawn for the rule\n            ",
            "format": "int32"
          },
          "startNumber": {
            "type": "integer",
            "description": "Minimum value or ball number for the rule\n            ",
            "format": "int32"
          },
          "endNumber": {
            "type": "integer",
            "description": "Maximum value or ball number for the rule\n            ",
            "format": "int32"
          }
        }
      },
      "TierModel": {
        "type": "object",
        "description": "Represents a prize definition\n            ",
        "additionalProperties": false,
        "required": [
          "tierCode"
        ],
        "properties": {
          "tierCode": {
            "type": "string",
            "description": "Unique identifier for the tier\n            ",
            "minLength": 1
          },
          "name": {
            "type": "string",
            "description": "The name of the Tier\n            ",
            "nullable": true
          },
          "prizeDescription": {
            "type": "string",
            "description": "Description of the prize\n            ",
            "nullable": true
          },
          "prize": {
            "type": "number",
            "description": "Optional value representing the US Dollar amount the prize pays\n            ",
            "format": "decimal",
            "nullable": true
          }
        }
      }
    },
    "securitySchemes": {
      "x-api-key": {
        "type": "apiKey",
        "description": "Submit this form to receive an API Key",
        "name": "x-api-key",
        "in": "header"
      }
    }
  },
  "security": [
    {
      "x-api-key": []
    }
  ],
  "tags": [
    {
      "name": "Get Grand Prize",
      "externalDocs": {
        "description": "Grand Prize API Overview",
        "url": "/grand-prize-api"
      }
    },
    {
      "name": "Get Winning Numbers",
      "externalDocs": {
        "description": "Winning Numbers API Overview",
        "url": "/numbers-api"
      }
    },
    {
      "name": "Get Winning Tiers",
      "externalDocs": {
        "description": "Winners Tier API Overview",
        "url": "/winners-api"
      }
    },
    {
      "name": "Get Draw Report",
      "externalDocs": {
        "description": "Draw Report API Overview",
        "url": "/draw-report-api"
      }
    },
    {
      "name": "Get Games",
      "externalDocs": {
        "description": "Games API Overview",
        "url": "/games-api"
      }
    }
  ]
}
```
