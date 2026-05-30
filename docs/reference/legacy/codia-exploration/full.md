# Introduction

Welcome to the Codia API! You can use our API to access VisualStruct API endpoints, which can recognize images, PDF, PSD and other format files and convert them into a unified DSL. Additionally, our API provides powerful image processing capabilities including background removal.

We have language bindings in Shell, Python, and JavaScript! You can view code examples in the dark area to the right, and you can switch the programming language of the examples with the tabs in the top right.

# Get Started

Getting started with the Codia API is easy! Follow these three simple steps to begin converting your Screenshots and PDFs into structured designs, or processing images with background removal.

## Step 1: Activate Your Subscription

Before you can start using the Codia API, you need to activate a subscription plan. Our API supports three distinct scenarios:

* **Screenshot to Design conversion**: Convert Screenshots (PNG, JPG, etc.) into design structures. [Learn more about Screenshot Visual Struct →](https://codia.ai/visual-struct)
* **PDF to Design conversion**: Convert PDF documents into design structures. [Learn more about PDF to Visual Struct →](https://codia.ai/pdf-to-visual-struct)
* **Background Removal**: Remove backgrounds from images to create transparent outputs.

Important: You need to purchase separate subscriptions for each scenario you plan to use. If you need multiple capabilities (Screenshot + Background Removal, and PDF), you'll need to activate subscriptions for each service.

## Step 2: Generate Your API Key

Once you've completed your subscription purchase:

1. Navigate to your **Personal Center** in your Codia account
2. Go to the [API Keys section](https://codia.ai/api-keys) to request an API key
3. Your generated API key will work for all scenarios (Screenshot, PDF conversion, and Background Removal)

![API Key Generation](https://static.codia.ai/resources/apikey.png)

Good news! Unlike subscriptions, your API key is universal and works across all scenarios once generated.

## Step 3: Make Your First API Call

You're now ready to start converting your content! Depending on your use case, you can:

* **Convert images**: Use the [Convert Image To Design](#convert-image-to-design) endpoint
* **Convert PDFs**: Use the [Convert PDF To Design](#convert-pdf-to-design) endpoint
* **Remove backgrounds**: Use the [Remove Background](#remove-background) endpoint

All endpoints are documented below with complete examples and parameter descriptions to help you get started quickly.

# Authentication

> To authorize, use this code:

```
Copy to Clipboard

# With shell, you can just pass the correct header with each request
curl "api_endpoint_here" \
  -H "Authorization: Bearer {codia_api_key}"
```

> Make sure to replace `{codia_api_key}` with your API key.

Codia uses API keys to allow access to the API. You can register a new Codia API key at our [developer portal](https://codia.ai).

Codia expects for the API key to be included in all API requests to the server in a header that looks like the following:

`Authorization: Bearer {codia_api_key}`

You must replace `{codia_api_key}` with your personal API key.

# VisualStruct API

## Convert Image To Design

```
Copy to Clipboard

curl 'https://api.codia.ai/v1/open/image_to_design' \
  -H 'Authorization: Bearer {codia_api_key}' \
  -H 'Content-Type: application/json' \
  --data '{
    "image_url": "your image url"
  }'
```

> The above command returns JSON structured like this:

```
Copy to Clipboard

{
  "code": 0,
  "message": "ok",
  "data": {
    // The Schema Object Here...
  }
}
```

This endpoint convert image to design.

### HTTP Request

`POST https://api.codia.ai/v1/open/image_to_design`

### Request Body

| Parameter | Default | Description |
| --- | --- | --- |
| image\_url | null | Image URL that needs to be converted into design. |

## Convert PDF To Design

```
Copy to Clipboard

curl 'https://api.codia.ai/v1/open/pdf_to_design' \
  -H 'Authorization: Bearer {codia_api_key}' \
  -H 'Content-Type: application/json' \
  --form 'pdf_file=@"xx.pdf"' \
  --form 'page_no="0"'
```

> The above command returns JSON structured like this:

```
Copy to Clipboard

{
  "code": 0,
  "message": "ok",
  "data": {
    "configuration": {
      "scalingFactor": 1,
      "baseWidth": 1940,
      "measurementUnit": "px"
    },
    "pages": [
      {
        // The Schema Object Here...
      }
    ],
    "size": {
      "height": 1080,
      "width": 1940
    }
  }
}
```

This endpoint convert pdf to design.

### HTTP Request

`POST https://api.codia.ai/v1/open/pdf_to_design`

### Request Body

| Parameter | Default | Description |
| --- | --- | --- |
| pdf\_file | null | PDF file that needs to be converted into design. |
| page\_no | null | Pages index of the PDF that need to be converted. Example: [0, 1] |

## Remove Background

```
Copy to Clipboard

curl 'https://api.codia.ai/v1/open/remove_bg' \
  -H 'Authorization: Bearer {codia_api_key}' \
  -H 'Content-Type: application/json' \
  --data '{
    "image_url": "your image url"
  }'
```

> The above command returns JSON structured like this:

```
Copy to Clipboard

{
  "code": 0,
  "message": "ok",
  "data": {
    "image_url": "https://processed-image-url.com/result.png"
  }
}
```

This endpoint removes the background from an image, returning a transparent background version.

### HTTP Request

`POST https://api.codia.ai/v1/open/remove_bg`

### Request Body

| Parameter | Default | Description |
| --- | --- | --- |
| image\_url | null | Image URL that needs background removal. |

### Response Data

| Field | Type | Description |
| --- | --- | --- |
| image\_url | string | URL of the processed image with transparent background |

# MCP Support

## What is MCP (Model Context Protocol)

MCP (Model Context Protocol) is an open-source standard for connecting AI applications to external systems.
Using MCP, AI applications like Cursor, Claude or ChatGPT can connect to data sources (e.g. local files, databases), tools (e.g. search engines, calculators) and workflows (e.g. specialized prompts)—enabling them to access key information and perform tasks.

The Codia MCP Server acts as a bridge between AI clients and Codia's Visual Struct API, providing standardized interfaces that ensure seamless communication between models and tools.

Learn more: [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/getting-started/intro)

## Codia MCP Server Overview

The Codia MCP Server is a specialized MCP implementation that provides AI applications with direct access to Codia's Visual Struct capabilities. It enables AI models to:

* **Analyze UI Screenshots**: Convert screenshots into structured design data with 95%+ accuracy
* **Process PDF Documents**: Extract structured data from PDF files including text, vectors, and layouts
* **Remove Backgrounds**: Automatically remove backgrounds from images for transparent outputs
* **Generate Structured Output**: Return JSON, SVG, and Figma-compatible structured data
* **Seamless Integration**: Work directly within AI workflows without manual API calls

### Architecture

AI Application (Cursor/Claude)

↓ MCP Protocol

Codia MCP Server

↓ HTTPS API Calls

Codia Visual Struct API

↓ Structured Data

AI Application Response

## Features & Capabilities

### 🖼️ Image Analysis

* **Screenshot Recognition**: Analyze UI screenshots and mockups
* **Component Detection**: Identify buttons, forms, navigation, and other UI elements
* **Layout Analysis**: Extract positioning, spacing, and hierarchical relationships
* **Style Extraction**: Capture colors, fonts, sizes, and visual properties

### 📄 PDF Processing

* **PDF Document Analysis**: Convert PDF documents into structured design data
* **Multi-page Support**: Process specific pages or entire PDF documents
* **Vector Graphics**: Preserve vector elements, paths, and shapes from PDFs
* **Text Extraction**: Extract text content with formatting and positioning

### 🎨 Image Processing

* **Background Removal**: Automatically remove backgrounds from images
* **High-Quality Output**: Maintain image quality during background removal
* **Format Support**: Support for PNG, JPG, and other common image formats

## Installation & Setup

### Prerequisites

* Valid Codia API subscription (Screenshot conversion + Background removal, or PDF conversion)
* Codia API key from [API Keys section](https://codia.ai/api-keys)
* Compatible AI application (Cursor, Claude Desktop, etc.)

### Configuration in Cursor

### 1. Project-level Configuration

Create `.cursor/mcp.json` in your project root:

```
Copy to Clipboard

{
  "mcpServers": {
    "visual_struct_mcp": {
      "url": "https://mcp.codia.ai",
      "headers": {
        "Authorization": "Bearer ${CODIA_API_KEY}"
      }
    }
  }
}
```

### 2. Global Configuration

Create `~/.cursor/mcp.json` in your home directory for system-wide access:

```
Copy to Clipboard

{
  "mcpServers": {
    "visual_struct_mcp": {
      "url": "https://mcp.codia.ai",
      "headers": {
        "Authorization": "Bearer ${CODIA_API_KEY}"
      }
    }
  }
}
```

### 3. Environment Variables

Set your API key as an environment variable:

```
Copy to Clipboard

# Add to your shell profile (.bashrc, .zshrc, etc.)
export CODIA_API_KEY="your_api_key_here"
```

## Usage Examples

### Basic Image Analysis

```
Copy to Clipboard

User: Analyze this screenshot and tell me about its structure
[Attaches screenshot image]

AI: I'll analyze this screenshot using the Codia Visual Struct API...
[MCP Server processes the image and returns structured data]

The screenshot shows a modern web application with:
- Header navigation with logo and menu items
- Main content area with card-based layout
- Sidebar with filtering options
- Footer with social links
```

### PDF Document Analysis

```
Copy to Clipboard

User: Convert pages 0-2 of this PDF into structured design data
[Attaches PDF document]

AI: I'll process this PDF using the Codia Visual Struct API...
[MCP Server processes the PDF and returns structured data]

The PDF contains 3 pages with:
- Page 1: Title page with logo and heading
- Page 2: Content layout with text blocks and vector diagrams
- Page 3: Footer section with contact information

The structured data includes:
- Text content with formatting and positioning
- Vector graphics (shapes, paths, lines)
- Layout hierarchy for each page
```

### Background Removal

```
Copy to Clipboard

User: Remove the background from this product image
[Attaches product image]

AI: I'll remove the background using the Codia Remove Background API...
[MCP Server processes the image]

Background removal complete! The image now has a transparent background,
making it perfect for use in:
- E-commerce product listings
- Marketing materials
- Web design compositions
```

## Available Tools

The Codia MCP Server provides the following tools to AI applications:

### `visual_struct_image`

Converts images into structured design data.

**Parameters:**
- `image_url` (string): URL of the image to analyze

**Returns:**
- Structured JSON with component hierarchy
- Style information (colors, fonts, spacing)
- Layout data (positioning, dimensions)

### `visual_struct_pdf`

Converts PDF documents into structured design data.

**Parameters:**
- `pdf_file` (file): PDF file to analyze
- `page_no` (array): Page indices to convert (e.g., [0, 1] for first two pages)

**Returns:**
- Structured JSON with page configurations
- Vector graphics data (paths, shapes)
- Text content with formatting
- Layout information for each page

### `remove_background`

Removes background from images automatically.

**Parameters:**
- `image_url` (string): URL of the image to process

**Returns:**
- Processed image URL with transparent background

## Error Handling & Troubleshooting

### Common Issues

#### Authentication Errors

```
Copy to Clipboard

Error: Unauthorized (401)
```

**Solution:** Verify your API key is correct and has active subscription.

#### Rate Limiting

```
Copy to Clipboard

Error: Too many requests (429)
```

**Solution:** Implement request throttling or upgrade your subscription plan.

### Debug Mode

Enable detailed logging by setting environment variable:

```
Copy to Clipboard

export MCP_DEBUG=true
```

### Support Resources

* [Codia API Documentation](https://developer.codia.ai)
* [MCP Protocol Specification](https://modelcontextprotocol.io)
* [Cursor MCP Guide](https://cursor.com/docs/context/mcp)

## Best Practices

### Performance Optimization

* **Image Compression**: Optimize images before processing to reduce latency
* **Caching**: Cache frequently used results to avoid redundant API calls

### Security

* **API Key Protection**: Never commit API keys to version control
* **Environment Variables**: Use secure environment variable management
* **Access Control**: Limit MCP server access to authorized applications

### Quality Assurance

* **Input Validation**: Verify image quality and format before processing
* **Result Verification**: Review structured output for accuracy
* **Iterative Refinement**: Use feedback to improve conversion quality

For more detailed configuration options, see: [Cursor MCP Configuration Guide](https://cursor.com/docs/context/mcp#mcpjson)

# The Schema Object

## Overview

The Visual Element Schema is a comprehensive data structure for describing user interface elements and their properties. This schema provides a standardized approach to represent UI components, their layout configurations, styling properties, and content definitions.

## Root Structure

```
Copy to Clipboard

{
  "visualElement": {
    // Main UI structure definition
  },
  "configuration": {
    // Global configuration options
  }
}
```

### Top-Level Fields

| Field Name | Type | Description | Required |
| --- | --- | --- | --- |
| `visualElement` | `VisualElement` | Main UI structure definition | Yes |
| `configuration` | `Configuration` | Global configuration options | No |

## VisualElement Structure

The `VisualElement` is the core data structure describing a single UI element and its properties.

### Basic Fields

| Field Name | Type | Description | Required | PDF Support |
| --- | --- | --- | --- | --- |
| `elementId` | `string` | Unique element identifier | Yes | ✓ |
| `elementName` | `string` | Element display name | Yes | ✓ |
| `elementType` | `string` | Element type | Yes | ✓ |
| `displayName` | `string` | English display name | No | ✓ |
| `layoutConfig` | `LayoutConfiguration` | Layout configuration | Yes | ✓ |
| `styleConfig` | `VisualStyle` or `PdfVisualStyle` | Style configuration | Yes | ✓ |
| `processingMeta` | `ProcessingMetadata` | Processing metadata | Yes | ✓ |
| `childElements` | `VisualElement[]` or `PdfVisualElement[]` | Child elements list | No | ✓ |
| `contentData` | `ElementContent` or `PdfElementContent` | Content data | No | ✓ |
| `componentSpec` | `ComponentDefinition` | Component specification | No | ✓ |
| `boundingBox` | `mixed` | **PDF-specific**: Element bounding box coordinates | No | PDF only |
| `displayOrder` | `number` | **PDF-specific**: Element display order | No | PDF only |

### Example Structure

```
Copy to Clipboard

{
  "elementId": "element_001",
  "elementName": "Main Container",
  "elementType": "Body",
  "displayName": "Primary Layout Container",
  "layoutConfig": { /* Layout configuration */ },
  "styleConfig": { /* Style configuration */ },
  "processingMeta": { /* Processing metadata */ },
  "childElements": [ /* Child elements */ ],
  "contentData": { /* Content data */ },
  "boundingBox": [0, 0, 100, 100],
  "displayOrder": 1
}
```

## Element Types

Supported UI element types in the schema:

### Type Values

| Type | Description | Usage | PDF Support |
| --- | --- | --- | --- |
| `Body` | Page or container root element | Main page structure | ✓ |
| `Layer` | Generic container for organizing elements | Layout containers | ✓ |
| `Image` | Image display element | Visual content | ✓ |
| `Text` | Text display element | Textual content | ✓ |
| `Component` | Reusable custom component | Custom components | ✓ |
| `Vector` | **PDF-specific**: Vector graphics element | Vector drawings, shapes | PDF only |
| `Group` | **PDF-specific**: Grouped elements | Element collections | PDF only |

### Example

```
Copy to Clipboard

{
  "elementType": "Panel",
  "elementName": "Header Section",
  "displayName": "Top Navigation Area"
}
```

## Layout Configuration

The `LayoutConfiguration` controls element positioning and layout behavior.

### Field Structure

| Field Name | Type | Description | Required |
| --- | --- | --- | --- |
| `positionMode` | `string` | Positioning mode | Yes |
| `flexibleMode` | `string` | Flexible layout type | No |
| `flexAttributes` | `Object` | Flexible layout attributes | No |
| `absoluteAttrs` | `Object` | Absolute positioning attributes | No |

### Position Modes

* **`"Normal"`**: Standard document flow
* **`"Absolute"`**: Absolute positioning
* **`"Relative"`**: Relative positioning
* **`"Flex"`**: Flexible box layout

### Flex Attributes Example

```
Copy to Clipboard

{
  "flexAttributes": {
    "alignItems": "center",
    "justifyContent": "space-between",
    "flexDirection": "column",
    "flexWrap": "nowrap"
  }
}
```

### Absolute Positioning Example

```
Copy to Clipboard

{
  "absoluteAttrs": {
    "align": ["LEFT", "TOP"],
    "coord": [0, 0],
    "orginCoord": [0, 0]
  }
}
```

## Visual Style Configuration

The `VisualStyle` defines visual styling properties for elements.

### Main Style Fields

| Field Name | Type | Description | Required | PDF Support |
| --- | --- | --- | --- | --- |
| `widthSpec` | `Object` | Width specifications | Yes | ✓ |
| `heightSpec` | `Object` | Height specifications | Yes | ✓ |
| `textConfig` | `Object` | Text styling configuration | No | ✓ |
| `borderConfig` | `Object` | Border styling configuration | No | ✓ |
| `backgroundSpec` | `Object` | Background specifications | No | ✓ |
| `effectsList` | `Array` | Visual effects list | No | ✓ |
| `textColor` | `VisualColor` | Text color settings | No | ✓ |
| `paddingValues` | `mixed` | Padding values | No | ✓ |
| `opacityLevel` | `number` | Opacity level (0-255) | No | ✓ |
| `overflowMode` | `Array` | Overflow handling mode | No | ✓ |
| `rotationAngle` | `number` | Rotation angle in degrees | No | ✓ |
| `textDetection` | `Object` | Text detection metadata | No | ✓ |
| `textExtraction` | `Object` | Text extraction metadata | No | ✓ |

### PDF-Specific Style Fields

The following fields are available only in PDF processing scenarios:

| Field Name | Type | Description |
| --- | --- | --- |
| `characterData` | `Object` | **PDF-specific**: Character-level styling data |
| `transformMatrix` | `number[]` | **PDF-specific**: Transformation matrix |
| `cornerRadius` | `number` | **PDF-specific**: Corner radius value |
| `isRightToLeft` | `boolean` | **PDF-specific**: Right-to-left text direction |
| `extendedMatrix` | `string` | **PDF-specific**: Extended transformation matrix |

### Size Configuration

```
Copy to Clipboard

{
  "widthSpec": {
    "sizing": "FIXED",    // FIXED, FILL, FIT_CONTENT
    "value": 100
  },
  "heightSpec": {
    "sizing": "FILL",
    "value": 200
  }
}
```

### Text Configuration

```
Copy to Clipboard

{
  "textConfig": {
    "fontSize": 16,
    "fontStyle": "normal",        // normal, bold, italic, semi_bold
    "textAlign": ["LEFT", "CENTER"],
    "fontFamily": "Arial",
    "lineHeight": 1.5,
    "letterSpacing": 0
  }
}
```

### Border Configuration

```
Copy to Clipboard

{
  "borderConfig": {
    "borderWidth": 2,
    "borderStyle": "solid",
    "borderColor": {
      "rgbValues": [128, 128, 128],
      "hexCode": "#808080"
    },
    "borderRadius": [10, 10, 10, 10]
  }
}
```

### Background Specifications

#### Solid Color Background

```
Copy to Clipboard

{
  "backgroundSpec": {
    "type": "COLOR",
    "backgroundColor": {
      "rgbValues": [255, 255, 255],
      "hexCode": "#ffffff"
    }
  }
}
```

#### Image Background

```
Copy to Clipboard

{
  "backgroundSpec": {
    "type": "IMAGE",
    "imageUrl": "https://example.com/bg.jpg",
    "backgroundSize": "cover",
    "backgroundPosition": "center",
    "backgroundRepeat": "no-repeat"
  }
}
```

#### Gradient Background

```
Copy to Clipboard

{
  "backgroundSpec": {
    "type": "LINEAR_GRADIENT",
    "deg": 45,
    "gradientStops": [
      {"color": {"rgbValues": [255, 0, 0]}, "position": 0},
      {"color": {"rgbValues": [0, 0, 255]}, "position": 100}
    ]
  }
}
```

### PDF-Specific Style Example

```
Copy to Clipboard

{
  "styleConfig": {
    "widthSpec": {"sizing": "FIXED", "value": 200},
    "heightSpec": {"sizing": "FIXED", "value": 100},
    "characterData": {
      "0": {"size": 12, "fontFamily": "Arial"},
      "1": {"size": 14, "fontFamily": "Bold"}
    },
    "transformMatrix": [1.0, 0.0, 0.0, 1.0, 50.0, 100.0],
    "cornerRadius": 5,
    "isRightToLeft": false,
    "extendedMatrix": "matrix(1,0,0,1,0,0)"
  }
}
```

## Color Definition

The `VisualColor` structure supports multiple color representation formats.

### Color Fields

| Field Name | Type | Description | Example |
| --- | --- | --- | --- |
| `rgbValues` | `number[]` | RGB values array | `[255, 128, 0]` |
| `hexCode` | `string` | Hexadecimal color code | `"#ff8000"` |

### Example

```
Copy to Clipboard

{
  "rgbValues": [255, 128, 0],
  "hexCode": "#ff8000"
}
```

## Element Content

The `ElementContent` defines the actual content of elements.

### Content Fields

| Field Name | Type | Description | Applicable Elements | PDF Support |
| --- | --- | --- | --- | --- |
| `textValue` | `string` | Text content | Text | ✓ |
| `imageSource` | `string` | Image URL source | Image | ✓ |
| `colorReference` | `string` | Color token reference | Any | ✓ |
| `componentReference` | `string` | Component reference ID | Component | ✓ |
| `componentAttributes` | `Object` | Component attributes | Component | ✓ |

### PDF-Specific Content Fields

The following content fields are available only in PDF processing scenarios:

| Field Name | Type | Description | Applicable Elements |
| --- | --- | --- | --- |
| `vectorData` | `VectorData` | **PDF-specific**: Vector graphics data | Vector/Shape |
| `maskingMode` | `string` | **PDF-specific**: Masking mode | Any |
| `blendingType` | `string` | **PDF-specific**: Blending mode | Any |
| `svgTemplate` | `string` | **PDF-specific**: SVG template string | Vector/Shape |
| `imageData` | `string` | **PDF-specific**: Base64 encoded image data | Image |

### Content Examples

#### Text Content

```
Copy to Clipboard

{
  "textValue": "Welcome to our platform",
  "colorReference": "primary_text_color"
}
```

#### Image Content

```
Copy to Clipboard

{
  "imageSource": "https://example.com/hero-image.jpg",
  "imageData": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ..."
}
```

#### PDF Vector Content

```
Copy to Clipboard

{
  "vectorData": {
    "pathItems": [
      {
        "pathType": "l",
        "coordinates": [
          {"xPosition": 0, "yPosition": 0},
          {"xPosition": 100, "yPosition": 100}
        ]
      }
    ],
    "evenOddRule": false,
    "layerIndex": 1,
    "vectorType": "path",
    "strokeOpacity": 1.0,
    "strokeColor": {
      "rgbValues": [0, 123, 255],
      "hexCode": "#007bff"
    },
    "strokeWidth": 2.0,
    "lineCapStyle": "round",
    "lineJoinStyle": "round",
    "isClosedPath": false
  },
  "maskingMode": "normal",
  "blendingType": "multiply"
}
```

#### Component Content

```
Copy to Clipboard

{
  "componentReference": "button_primary",
  "componentAttributes": {
    "variant": {"type": "primary"},
    "size": {"value": "large"},
    "action": {"handler": "submitForm"}
  }
}
```

## PDF Vector Data Structure

**Note**: The following structures are specific to PDF processing scenarios.

### VectorData Structure

| Field Name | Type | Description |
| --- | --- | --- |
| `pathItems` | `PathItem[]` | Array of path elements |
| `evenOddRule` | `boolean` | Even-odd fill rule |
| `layerDepth` | `string` | Layer depth identifier |
| `layerIndex` | `number` | Layer index number |
| `vectorType` | `string` | Vector type identifier |
| `strokeOpacity` | `number` | Stroke opacity (0.0-1.0) |
| `strokeColor` | `VisualColor` | Stroke color |
| `fillColor` | `VisualColor` | Fill color |
| `fillOpacity` | `number` | Fill opacity (0.0-1.0) |
| `lineCapStyle` | `string` | Line cap style |
| `lineJoinStyle` | `string` | Line join style |
| `dashPattern` | `number[]` | Dash pattern array |
| `strokeWidth` | `number` | Stroke width |
| `isClosedPath` | `boolean` | Whether path is closed |

### PathItem Structure

| Field Name | Type | Description |
| --- | --- | --- |
| `pathType` | `string` | Path type ("l" for line, "c" for curve) |
| `coordinates` | `PositionData[]` | Array of position coordinates |

### PositionData Structure

| Field Name | Type | Description |
| --- | --- | --- |
| `xPosition` | `number` | X coordinate |
| `yPosition` | `number` | Y coordinate |

### PDF Vector Example

```
Copy to Clipboard

{
  "vectorData": {
    "pathItems": [
      {
        "pathType": "l",
        "coordinates": [
          {"xPosition": 50.0, "yPosition": 50.0},
          {"xPosition": 250.0, "yPosition": 50.0}
        ]
      },
      {
        "pathType": "c",
        "coordinates": [
          {"xPosition": 250.0, "yPosition": 50.0},
          {"xPosition": 275.0, "yPosition": 25.0},
          {"xPosition": 275.0, "yPosition": 75.0},
          {"xPosition": 250.0, "yPosition": 100.0}
        ]
      }
    ],
    "evenOddRule": false,
    "layerIndex": 1,
    "vectorType": "path",
    "strokeOpacity": 1.0,
    "strokeColor": {
      "rgbValues": [0, 123, 255],
      "hexCode": "#007bff"
    },
    "fillColor": {
      "rgbValues": [255, 255, 255],
      "hexCode": "#ffffff"
    },
    "fillOpacity": 0.5,
    "lineCapStyle": "round",
    "lineJoinStyle": "round",
    "dashPattern": [5, 3],
    "strokeWidth": 2.0,
    "isClosedPath": false
  }
}
```

## Component Definition

The `ComponentDefinition` structure for reusable components.

### Component Fields

| Field Name | Type | Description |
| --- | --- | --- |
| `componentId` | `string` | Component identifier |
| `componentName` | `string` | Component display name |
| `sourceCode` | `string` | Component implementation code |
| `configOptions` | `Object` | Configuration options schema |

### Example

```
Copy to Clipboard

{
  "componentId": "interactive_button",
  "componentName": "Interactive Button Component",
  "sourceCode": "/* React component implementation */",
  "configOptions": {
    "variant": "string",
    "size": "string",
    "disabled": "boolean",
    "onClick": "function"
  }
}
```

## Processing Metadata

The `ProcessingMetadata` contains technical processing information.

### Metadata Fields

| Field Name | Type | Description |
| --- | --- | --- |
| `surfaceArea` | `number` | Element surface area in pixels |
| `detectionScore` | `number` | Detection confidence score (0.0-1.0) |
| `textContainerized` | `boolean` | Whether text is containerized |

### Example

```
Copy to Clipboard

{
  "surfaceArea": 960000,
  "detectionScore": 0.95,
  "textContainerized": true
}
```

## Global Configuration

The `Configuration` object contains global settings.

### Configuration Fields

| Field Name | Type | Description | Default |
| --- | --- | --- | --- |
| `baseWidth` | `number` | Base design width | 375 |
| `measurementUnit` | `string` | Measurement unit | "px" |
| `scalingFactor` | `number` | Scaling factor | 1 |

### Example

```
Copy to Clipboard

{
  "baseWidth": 782,
  "measurementUnit": "px",
  "scalingFactor": 1
}
```

## Complete Example

### PDF Document Structure Example

```
Copy to Clipboard

{
  "visualElement": {
    "elementId": "pdf_page_1",
    "elementName": "PDF Document Page",
    "elementType": "Panel",
    "displayName": "First Page",
    "displayOrder": 0,
    "boundingBox": [0, 0, 595, 842],
    "layoutConfig": {
      "positionMode": "Normal",
      "flexibleMode": "Absolute"
    },
    "styleConfig": {
      "widthSpec": {"sizing": "FIXED", "value": 595},
      "heightSpec": {"sizing": "FIXED", "value": 842},
      "backgroundSpec": {
        "type": "COLOR",
        "backgroundColor": {"rgbValues": [255, 255, 255]}
      }
    },
    "processingMeta": {
      "surfaceArea": 501490,
      "detectionScore": 0.92,
      "textContainerized": false
    },
    "childElements": [
      {
        "elementId": "vector_diagram",
        "elementName": "Process Diagram",
        "elementType": "Shape",
        "displayOrder": 1,
        "layoutConfig": {
          "positionMode": "Absolute",
          "absoluteAttrs": {
            "align": ["LEFT", "TOP"],
            "coord": [50, 100]
          }
        },
        "styleConfig": {
          "widthSpec": {"sizing": "FIXED", "value": 300},
          "heightSpec": {"sizing": "FIXED", "value": 200}
        },
        "processingMeta": {
          "surfaceArea": 60000,
          "detectionScore": 0.89,
          "textContainerized": false
        },
        "contentData": {
          "vectorData": {
            "pathItems": [
              {
                "pathType": "l",
                "coordinates": [
                  {"xPosition": 50.0, "yPosition": 50.0},
                  {"xPosition": 250.0, "yPosition": 50.0}
                ]
              }
            ],
            "evenOddRule": false,
            "layerIndex": 1,
            "vectorType": "path",
            "strokeOpacity": 1.0,
            "strokeColor": {
              "rgbValues": [0, 123, 255],
              "hexCode": "#007bff"
            },
            "strokeWidth": 2.0,
            "lineCapStyle": "round",
            "lineJoinStyle": "round",
            "isClosedPath": false
          }
        }
      }
    ]
  },
  "configuration": {
    "baseWidth": 595,
    "measurementUnit": "pt",
    "scalingFactor": 1
  }
}
```

# Codia Figma SDK

## Overview

Automatically generate Figma designs from UI screenshots. Call the Codia API to get design data, then generate corresponding components in Figma.

## Usage Flow

### 1. Plugin UI (ui.html)

Create the plugin user interface with a button to trigger design generation. When users click the button, it calls the Codia API to fetch design data and sends the data to the plugin main thread for processing.

```
Copy to Clipboard

<!DOCTYPE html>
<html>
  <head>
    <title>Codia Design Generator</title>
  </head>
  <body>
    <button id="generateBtn">Generate Design</button>

    <script>
      const generateBtn = document.getElementById("generateBtn");

      // Configuration
      const CODIA_API_KEY = "YOUR_API_KEY_HERE";
      const IMAGE_URL = "https://your-image-url.com/screenshot.png";

      // Call Codia API to get design data
      async function fetchDSLFromCodia() {
        try {
          const response = await fetch(
            "https://api.codia.ai/v1/open/image_to_design",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${CODIA_API_KEY}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                image_url: IMAGE_URL,
              }),
            }
          );

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const data = await response.json();

          if (data.code !== 0) {
            throw new Error(data.message || "API request failed");
          }

          return data.data.visualElement;
        } catch (error) {
          console.error("Failed to fetch DSL from Codia:", error);
          throw error;
        }
      }

      // Generate design on button click
      generateBtn.addEventListener("click", async () => {
        try {
          const designData = await fetchDSLFromCodia();
          if (!designData) {
            return;
          }

          // Send message to plugin main thread
          parent.postMessage(
            {
              pluginMessage: {
                type: "generate-design",
                data: designData,
              },
            },
            "*"
          );
        } catch (error) {
          console.error("Error:", error);
        }
      });

      // Listen for plugin main thread responses
      window.addEventListener("message", (event) => {
        const msg = event.data.pluginMessage;
        if (msg && msg.type === "design-result") {
          if (msg.success) {
            console.log("Design generation successful!");
          } else {
            console.error("Generation failed:", msg.error);
          }
        }
      });
    </script>
  </body>
</html>
```

### 2. Install Dependencies

Install the Codia SDK dependency package, which provides core functionality for converting design data into Figma designs.

```
Copy to Clipboard

npm install figma-image-to-design
```

### 3. Plugin Main Thread Code (code.ts)

Write the plugin main thread code that handles receiving messages from the UI, processes design data using the Codia SDK, and generates corresponding Figma designs.

Important: Since Figma does not natively support TypeScript, this TypeScript code needs to be compiled to JavaScript before it can be used in a Figma plugin.

```
Copy to Clipboard

// Import Codia SDK
import { DesignGenerator } from "figma-image-to-design";

// Show plugin UI
figma.showUI(__html__, { width: 300, height: 200 });

// Listen to messages from UI
figma.ui.onmessage = async (msg) => {
  if (msg.type === "generate-design") {
    try {
      // Use Codia SDK to generate design
      const result = await DesignGenerator.generateFromVisualElement(msg.data);

      if (result.status === "SUCCESS") {
        // Send success message back to UI
        figma.ui.postMessage({
          type: "design-result",
          success: true,
          result: result,
        });
      } else {
        // Send failure message back to UI
        figma.ui.postMessage({
          type: "design-result",
          success: false,
          error: result.message,
        });
      }
    } catch (error) {
      // Send error message back to UI
      figma.ui.postMessage({
        type: "design-result",
        success: false,
        error: error.message,
      });
    }
  }
};
```

## Result Structure

```
Copy to Clipboard

interface DesignGenerateResult {
  message: string; // Result message
  statusCode: number; // Status code
  status: "SUCCESS" | "SCRIPT_ERROR" | "CONVERSION_ERROR"; // Generation status
}
```

## Core Flow

1. **UI sends message**: User clicks button → Fetch API data → Send to main thread via `parent.postMessage()`
2. **Main thread receives**: `figma.ui.onmessage` listens for messages → Process data to generate design
3. **Result feedback**: Main thread sends result back to UI via `figma.ui.postMessage()`

## Notes

* Replace `YOUR_API_KEY_HERE` with your actual API Key
* Replace the image URL with your actual screenshot URL

## Demo Project

To help developers quickly integrate Codia SDK, we provide a complete Figma plugin project.

**[Download codia-sdk-demo.zip](https://static.codia.ai/resources/codia-sdk-demo.zip)**

The project includes complete plugin source code, UI interface, pre-configured build environment (Webpack + TypeScript), and Codia API integration examples.

After downloading and extracting, follow the **README.md** in the project root directory to get started quickly.

# Errors

The Codia API uses the following error codes:

| Error Code | Meaning |
| --- | --- |
| 400 | Bad Request -- Your request is invalid. |
| 401 | Unauthorized -- Your API key is wrong. |
| 402 | PaymentRequired -- Your credit is insufficient. |
| 403 | Forbidden -- The api requested is hidden for administrators only. |
| 404 | Not Found -- The specified api could not be found. |
| 405 | Method Not Allowed -- You tried to access an api with an invalid method. |
| 406 | Not Acceptable -- You requested a format that isn't json. |
| 429 | Too Many Requests -- You're requesting too many images! Slow down! |
| 500 | Internal Server Error -- We had a problem with our server. Try again later. |
| 503 | Service Unavailable -- We're temporarily offline for maintenance. Please try again later. |
