下面继续输出第六份核心文档：

**`03_DSL规范/12_DSL_v0.1_完整示例.md`**

~~~markdown
# DSL v0.1 完整示例

文档名称：DSL v0.1 完整示例  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 核心协议示例文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于提供一份完整的 DSL v0.1 示例，帮助后端、Figma 插件端、Renderer 开发人员理解：

```text
1. DSL 顶层结构如何组织
2. page / assets / root / meta 如何配合
3. Frame / Text / Shape / Image / Icon / Line 如何表达
4. 原图参考层如何放置
5. fallback 区域如何表达
6. Renderer 应如何消费 DSL
~~~

该示例不是最终 UI 效果标准，而是第一版 MVP 的数据结构参考。

------

## 2. 示例页面说明

本示例模拟一个移动端首页页面，包含：

```text
状态栏 / 导航栏
搜索框
Banner
商品卡片
底部 TabBar
隐藏原图参考层
局部 fallback 区域
```

页面基础信息：

```text
设计稿原图尺寸：780 x 1688
Figma 目标尺寸：390 x 844
scaleFactor：2
页面类型：mobile
```

------

## 3. 完整 DSL 示例

```json
{
  "version": "0.1",
  "taskId": "task_demo_home_001",
  "page": {
    "name": "mobile_home_demo",
    "width": 390,
    "height": 844,
    "originalWidth": 780,
    "originalHeight": 1688,
    "scaleFactor": 2,
    "viewportHeight": 844,
    "isScrollable": false,
    "background": {
      "type": "color",
      "value": "#F7F8FA"
    },
    "safeArea": {
      "top": 44,
      "bottom": 34
    }
  },
  "assets": [
    {
      "assetId": "asset_original",
      "type": "image",
      "role": "original",
      "url": "http://localhost:8000/files/uploads/task_demo_home_001/original.png",
      "format": "png",
      "width": 390,
      "height": 844,
      "storage": "local",
      "meta": {
        "description": "Original uploaded PNG scaled to Figma coordinate size"
      }
    },
    {
      "assetId": "asset_banner_001",
      "type": "image",
      "role": "banner_image",
      "url": "http://localhost:8000/files/assets/task_demo_home_001/banner_001.jpg",
      "format": "jpeg",
      "width": 358,
      "height": 140,
      "storage": "local",
      "meta": {
        "cropBBox": [32, 240, 748, 520],
        "padding": 2
      }
    },
    {
      "assetId": "asset_product_001",
      "type": "image",
      "role": "product_image",
      "url": "http://localhost:8000/files/assets/task_demo_home_001/product_001.jpg",
      "format": "jpeg",
      "width": 96,
      "height": 96,
      "storage": "local",
      "meta": {
        "cropBBox": [32, 600, 224, 792],
        "padding": 4
      }
    },
    {
      "assetId": "asset_product_002",
      "type": "image",
      "role": "product_image",
      "url": "http://localhost:8000/files/assets/task_demo_home_001/product_002.jpg",
      "format": "jpeg",
      "width": 96,
      "height": 96,
      "storage": "local",
      "meta": {
        "cropBBox": [32, 820, 224, 1012],
        "padding": 4
      }
    },
    {
      "assetId": "asset_fallback_banner_deco",
      "type": "image",
      "role": "fallback_region",
      "url": "http://localhost:8000/files/assets/task_demo_home_001/fallback_banner_deco.png",
      "format": "png",
      "width": 358,
      "height": 140,
      "storage": "local",
      "meta": {
        "fallback": true,
        "reason": "complex_banner_decoration"
      }
    }
  ],
  "root": {
    "id": "root",
    "type": "frame",
    "role": "screen",
    "name": "mobile_home_demo",
    "layout": {
      "x": 0,
      "y": 0,
      "width": 390,
      "height": 844
    },
    "style": {
      "fill": "#F7F8FA",
      "visible": true
    },
    "children": [
      {
        "id": "original_ref",
        "type": "image",
        "role": "original_reference",
        "name": "Original PNG Reference",
        "layout": {
          "x": 0,
          "y": 0,
          "width": 390,
          "height": 844
        },
        "source": {
          "assetId": "asset_original"
        },
        "style": {
          "visible": false,
          "opacity": 0.5
        },
        "imageFill": {
          "mode": "fill"
        },
        "meta": {
          "fallback": false,
          "description": "Hidden original PNG reference layer"
        }
      },
      {
        "id": "status_bar",
        "type": "image",
        "role": "status_bar",
        "name": "Status Bar Image",
        "layout": {
          "x": 0,
          "y": 0,
          "width": 390,
          "height": 44
        },
        "source": {
          "assetId": "asset_original"
        },
        "style": {
          "visible": true,
          "opacity": 1,
          "clipContent": true
        },
        "imageFill": {
          "mode": "fill"
        },
        "meta": {
          "fallback": true,
          "reason": "status_bar_kept_as_image",
          "sourceBBox": [0, 0, 780, 88]
        }
      },
      {
        "id": "nav_bar",
        "type": "frame",
        "role": "navigation_bar",
        "name": "Navigation Bar",
        "layout": {
          "x": 0,
          "y": 44,
          "width": 390,
          "height": 44
        },
        "style": {
          "fill": "#FFFFFF"
        },
        "children": [
          {
            "id": "nav_title",
            "type": "text",
            "role": "title_text",
            "name": "Page Title",
            "layout": {
              "x": 160,
              "y": 55,
              "width": 70,
              "height": 22
            },
            "content": {
              "text": "首页"
            },
            "style": {
              "fontFamily": "PingFang SC",
              "fontSize": 17,
              "fontWeight": 600,
              "lineHeight": 22,
              "color": "#111111",
              "textAlign": "center"
            },
            "meta": {
              "confidence": 0.95,
              "ocrConfidence": 0.97,
              "sourceBBox": [320, 110, 460, 154]
            }
          }
        ],
        "meta": {
          "confidence": 0.92,
          "positionHint": "fixed_top"
        }
      },
      {
        "id": "content",
        "type": "frame",
        "role": "content",
        "name": "Content",
        "layout": {
          "x": 0,
          "y": 88,
          "width": 390,
          "height": 668
        },
        "style": {
          "fill": "#F7F8FA"
        },
        "children": [
          {
            "id": "search_bar",
            "type": "frame",
            "role": "search_bar",
            "name": "Search Bar",
            "layout": {
              "x": 16,
              "y": 100,
              "width": 358,
              "height": 40
            },
            "style": {
              "fill": "#FFFFFF",
              "radius": 20,
              "stroke": {
                "color": "#EEEEEE",
                "width": 1
              }
            },
            "children": [
              {
                "id": "search_icon",
                "type": "icon",
                "role": "search_icon",
                "name": "Search Icon",
                "layout": {
                  "x": 32,
                  "y": 112,
                  "width": 16,
                  "height": 16
                },
                "source": {
                  "kind": "builtin_svg",
                  "iconName": "search"
                },
                "style": {
                  "color": "#999999",
                  "opacity": 1
                },
                "meta": {
                  "confidence": 0.9
                }
              },
              {
                "id": "search_placeholder",
                "type": "text",
                "role": "placeholder_text",
                "name": "Search Placeholder",
                "layout": {
                  "x": 56,
                  "y": 109,
                  "width": 120,
                  "height": 22
                },
                "content": {
                  "text": "搜索商品"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 14,
                  "fontWeight": 400,
                  "lineHeight": 22,
                  "color": "#999999",
                  "textAlign": "left"
                },
                "meta": {
                  "confidence": 0.92,
                  "ocrConfidence": 0.94,
                  "semanticType": "placeholder"
                }
              }
            ],
            "meta": {
              "componentSpec": {
                "kind": "SearchBar",
                "variant": "default",
                "confidence": 0.92
              }
            }
          },
          {
            "id": "banner",
            "type": "image",
            "role": "banner_image",
            "name": "Banner Image",
            "layout": {
              "x": 16,
              "y": 156,
              "width": 358,
              "height": 140
            },
            "source": {
              "assetId": "asset_banner_001"
            },
            "style": {
              "radius": 12,
              "clipContent": true
            },
            "imageFill": {
              "mode": "fill"
            },
            "meta": {
              "fallback": true,
              "reason": "complex_banner_kept_as_image",
              "confidence": 0.78
            }
          },
          {
            "id": "section_title",
            "type": "text",
            "role": "section_title",
            "name": "Section Title",
            "layout": {
              "x": 16,
              "y": 316,
              "width": 120,
              "height": 24
            },
            "content": {
              "text": "推荐商品"
            },
            "style": {
              "fontFamily": "PingFang SC",
              "fontSize": 18,
              "fontWeight": 600,
              "lineHeight": 24,
              "color": "#111111",
              "textAlign": "left"
            },
            "meta": {
              "confidence": 0.94,
              "ocrConfidence": 0.96
            }
          },
          {
            "id": "product_card_001",
            "type": "frame",
            "role": "card",
            "name": "Product Card 01",
            "layout": {
              "x": 16,
              "y": 352,
              "width": 358,
              "height": 112
            },
            "style": {
              "fill": "#FFFFFF",
              "radius": 12,
              "shadow": [
                {
                  "type": "drop_shadow",
                  "x": 0,
                  "y": 4,
                  "blur": 12,
                  "spread": 0,
                  "color": "rgba(0,0,0,0.06)"
                }
              ]
            },
            "children": [
              {
                "id": "product_img_001",
                "type": "image",
                "role": "product_image",
                "name": "Product Image",
                "layout": {
                  "x": 28,
                  "y": 360,
                  "width": 96,
                  "height": 96
                },
                "source": {
                  "assetId": "asset_product_001"
                },
                "style": {
                  "radius": 8,
                  "clipContent": true
                },
                "imageFill": {
                  "mode": "fit"
                },
                "meta": {
                  "fallback": false,
                  "confidence": 0.88
                }
              },
              {
                "id": "product_title_001",
                "type": "text",
                "role": "title_text",
                "name": "Product Title",
                "layout": {
                  "x": 140,
                  "y": 365,
                  "width": 190,
                  "height": 22
                },
                "content": {
                  "text": "新鲜番茄 500g"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 16,
                  "fontWeight": 500,
                  "lineHeight": 22,
                  "color": "#111111",
                  "textAlign": "left"
                },
                "meta": {
                  "confidence": 0.91,
                  "ocrConfidence": 0.93
                }
              },
              {
                "id": "product_desc_001",
                "type": "text",
                "role": "body_text",
                "name": "Product Description",
                "layout": {
                  "x": 140,
                  "y": 392,
                  "width": 190,
                  "height": 18
                },
                "content": {
                  "text": "产地直发，新鲜采摘"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 12,
                  "fontWeight": 400,
                  "lineHeight": 18,
                  "color": "#888888",
                  "textAlign": "left"
                },
                "meta": {
                  "confidence": 0.87,
                  "ocrConfidence": 0.89
                }
              },
              {
                "id": "product_price_001",
                "type": "text",
                "role": "price_text",
                "name": "Product Price",
                "layout": {
                  "x": 140,
                  "y": 425,
                  "width": 80,
                  "height": 24
                },
                "content": {
                  "text": "¥12.90"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 18,
                  "fontWeight": 700,
                  "lineHeight": 24,
                  "color": "#FF4D4F",
                  "textAlign": "left"
                },
                "meta": {
                  "confidence": 0.94,
                  "ocrConfidence": 0.96,
                  "semanticType": "price",
                  "correctionPolicy": "no_free_rewrite"
                }
              },
              {
                "id": "buy_button_001",
                "type": "frame",
                "role": "button",
                "name": "Buy Button",
                "layout": {
                  "x": 292,
                  "y": 420,
                  "width": 66,
                  "height": 30
                },
                "style": {},
                "children": [
                  {
                    "id": "buy_button_bg_001",
                    "type": "shape",
                    "role": "button_background",
                    "name": "Button Background",
                    "layout": {
                      "x": 292,
                      "y": 420,
                      "width": 66,
                      "height": 30
                    },
                    "style": {
                      "fill": "#FF4D4F",
                      "radius": 15
                    }
                  },
                  {
                    "id": "buy_button_text_001",
                    "type": "text",
                    "role": "button_label",
                    "name": "Button Label",
                    "layout": {
                      "x": 307,
                      "y": 426,
                      "width": 36,
                      "height": 18
                    },
                    "content": {
                      "text": "购买"
                    },
                    "style": {
                      "fontFamily": "PingFang SC",
                      "fontSize": 13,
                      "fontWeight": 500,
                      "lineHeight": 18,
                      "color": "#FFFFFF",
                      "textAlign": "center"
                    }
                  }
                ],
                "meta": {
                  "componentSpec": {
                    "kind": "Button",
                    "variant": "primary",
                    "confidence": 0.9
                  }
                }
              }
            ],
            "meta": {
              "componentSpec": {
                "kind": "Card",
                "variant": "product",
                "confidence": 0.86
              }
            }
          },
          {
            "id": "product_card_002",
            "type": "frame",
            "role": "card",
            "name": "Product Card 02",
            "layout": {
              "x": 16,
              "y": 476,
              "width": 358,
              "height": 112
            },
            "style": {
              "fill": "#FFFFFF",
              "radius": 12,
              "shadow": [
                {
                  "type": "drop_shadow",
                  "x": 0,
                  "y": 4,
                  "blur": 12,
                  "spread": 0,
                  "color": "rgba(0,0,0,0.06)"
                }
              ]
            },
            "children": [
              {
                "id": "product_img_002",
                "type": "image",
                "role": "product_image",
                "name": "Product Image",
                "layout": {
                  "x": 28,
                  "y": 484,
                  "width": 96,
                  "height": 96
                },
                "source": {
                  "assetId": "asset_product_002"
                },
                "style": {
                  "radius": 8,
                  "clipContent": true
                },
                "imageFill": {
                  "mode": "fit"
                },
                "meta": {
                  "fallback": false,
                  "confidence": 0.86
                }
              },
              {
                "id": "product_title_002",
                "type": "text",
                "role": "title_text",
                "name": "Product Title",
                "layout": {
                  "x": 140,
                  "y": 489,
                  "width": 190,
                  "height": 22
                },
                "content": {
                  "text": "有机黄瓜 300g"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 16,
                  "fontWeight": 500,
                  "lineHeight": 22,
                  "color": "#111111",
                  "textAlign": "left"
                },
                "meta": {
                  "confidence": 0.9,
                  "ocrConfidence": 0.92
                }
              },
              {
                "id": "product_price_002",
                "type": "text",
                "role": "price_text",
                "name": "Product Price",
                "layout": {
                  "x": 140,
                  "y": 549,
                  "width": 80,
                  "height": 24
                },
                "content": {
                  "text": "¥8.80"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 18,
                  "fontWeight": 700,
                  "lineHeight": 24,
                  "color": "#FF4D4F",
                  "textAlign": "left"
                },
                "meta": {
                  "confidence": 0.94,
                  "ocrConfidence": 0.95,
                  "semanticType": "price",
                  "correctionPolicy": "no_free_rewrite"
                }
              }
            ],
            "meta": {
              "componentSpec": {
                "kind": "Card",
                "variant": "product",
                "confidence": 0.84
              }
            }
          }
        ]
      },
      {
        "id": "tab_bar",
        "type": "frame",
        "role": "tab_bar",
        "name": "TabBar",
        "layout": {
          "x": 0,
          "y": 756,
          "width": 390,
          "height": 88
        },
        "style": {
          "fill": "#FFFFFF",
          "shadow": [
            {
              "type": "drop_shadow",
              "x": 0,
              "y": -2,
              "blur": 8,
              "spread": 0,
              "color": "rgba(0,0,0,0.05)"
            }
          ]
        },
        "children": [
          {
            "id": "tab_home",
            "type": "frame",
            "role": "tab_item",
            "name": "Tab Item - Home Active",
            "layout": {
              "x": 0,
              "y": 756,
              "width": 97.5,
              "height": 54
            },
            "children": [
              {
                "id": "tab_home_icon",
                "type": "icon",
                "role": "home_icon",
                "name": "Home Icon",
                "layout": {
                  "x": 36.75,
                  "y": 766,
                  "width": 24,
                  "height": 24
                },
                "source": {
                  "kind": "builtin_svg",
                  "iconName": "home"
                },
                "style": {
                  "color": "#FF4D4F"
                }
              },
              {
                "id": "tab_home_text",
                "type": "text",
                "role": "tab_label",
                "name": "Home Label",
                "layout": {
                  "x": 34,
                  "y": 792,
                  "width": 30,
                  "height": 16
                },
                "content": {
                  "text": "首页"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 11,
                  "fontWeight": 500,
                  "lineHeight": 16,
                  "color": "#FF4D4F",
                  "textAlign": "center"
                }
              }
            ],
            "meta": {
              "state": "active"
            }
          },
          {
            "id": "tab_category",
            "type": "frame",
            "role": "tab_item",
            "name": "Tab Item - Category",
            "layout": {
              "x": 97.5,
              "y": 756,
              "width": 97.5,
              "height": 54
            },
            "children": [
              {
                "id": "tab_category_icon",
                "type": "icon",
                "role": "category_icon",
                "name": "Category Icon",
                "layout": {
                  "x": 134.25,
                  "y": 766,
                  "width": 24,
                  "height": 24
                },
                "source": {
                  "kind": "builtin_svg",
                  "iconName": "category"
                },
                "style": {
                  "color": "#999999"
                }
              },
              {
                "id": "tab_category_text",
                "type": "text",
                "role": "tab_label",
                "name": "Category Label",
                "layout": {
                  "x": 131,
                  "y": 792,
                  "width": 34,
                  "height": 16
                },
                "content": {
                  "text": "分类"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 11,
                  "fontWeight": 400,
                  "lineHeight": 16,
                  "color": "#999999",
                  "textAlign": "center"
                }
              }
            ],
            "meta": {
              "state": "inactive"
            }
          },
          {
            "id": "tab_cart",
            "type": "frame",
            "role": "tab_item",
            "name": "Tab Item - Cart",
            "layout": {
              "x": 195,
              "y": 756,
              "width": 97.5,
              "height": 54
            },
            "children": [
              {
                "id": "tab_cart_icon",
                "type": "icon",
                "role": "cart_icon",
                "name": "Cart Icon",
                "layout": {
                  "x": 231.75,
                  "y": 766,
                  "width": 24,
                  "height": 24
                },
                "source": {
                  "kind": "builtin_svg",
                  "iconName": "cart"
                },
                "style": {
                  "color": "#999999"
                }
              },
              {
                "id": "tab_cart_text",
                "type": "text",
                "role": "tab_label",
                "name": "Cart Label",
                "layout": {
                  "x": 229,
                  "y": 792,
                  "width": 34,
                  "height": 16
                },
                "content": {
                  "text": "购物车"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 11,
                  "fontWeight": 400,
                  "lineHeight": 16,
                  "color": "#999999",
                  "textAlign": "center"
                }
              }
            ],
            "meta": {
              "state": "inactive"
            }
          },
          {
            "id": "tab_profile",
            "type": "frame",
            "role": "tab_item",
            "name": "Tab Item - Profile",
            "layout": {
              "x": 292.5,
              "y": 756,
              "width": 97.5,
              "height": 54
            },
            "children": [
              {
                "id": "tab_profile_icon",
                "type": "icon",
                "role": "user_icon",
                "name": "User Icon",
                "layout": {
                  "x": 329.25,
                  "y": 766,
                  "width": 24,
                  "height": 24
                },
                "source": {
                  "kind": "builtin_svg",
                  "iconName": "user"
                },
                "style": {
                  "color": "#999999"
                }
              },
              {
                "id": "tab_profile_text",
                "type": "text",
                "role": "tab_label",
                "name": "Profile Label",
                "layout": {
                  "x": 326,
                  "y": 792,
                  "width": 34,
                  "height": 16
                },
                "content": {
                  "text": "我的"
                },
                "style": {
                  "fontFamily": "PingFang SC",
                  "fontSize": 11,
                  "fontWeight": 400,
                  "lineHeight": 16,
                  "color": "#999999",
                  "textAlign": "center"
                }
              }
            ],
            "meta": {
              "state": "inactive"
            }
          },
          {
            "id": "home_indicator",
            "type": "shape",
            "role": "home_indicator",
            "name": "Home Indicator",
            "layout": {
              "x": 128,
              "y": 826,
              "width": 134,
              "height": 5
            },
            "style": {
              "fill": "#000000",
              "radius": 999,
              "opacity": 1
            }
          }
        ],
        "meta": {
          "positionHint": "fixed_bottom",
          "componentSpec": {
            "kind": "TabBar",
            "confidence": 0.9
          }
        }
      }
    ]
  },
  "meta": {
    "createdAt": "2026-05-16T00:00:00Z",
    "source": "png",
    "platformHint": "mobile",
    "qualityFlags": [],
    "fallbackCount": 2,
    "elementCount": 52,
    "promptVersion": "semantic_analyzer_v0.1",
    "model": "gpt-5.5",
    "notes": "Demo DSL for MVP renderer implementation"
  }
}
```

------

## 4. 示例字段说明

### 4.1 version

```json
"version": "0.1"
```

表示当前 DSL 版本。
Renderer 必须检查该字段。

------

### 4.2 taskId

```json
"taskId": "task_demo_home_001"
```

用于后端任务追踪、资源归属、错误日志关联。

------

### 4.3 page

```json
"page": {
  "width": 390,
  "height": 844,
  "scaleFactor": 2
}
```

表示 Figma 最终画布尺寸和原图缩放关系。

这里原始 PNG 是：

```text
780 x 1688
```

目标 Figma Frame 是：

```text
390 x 844
```

所以：

```text
scaleFactor = 2
```

------

### 4.4 assets

`assets` 统一管理图片资源。

元素不直接强依赖 URL，而是通过：

```json
"source": {
  "assetId": "asset_product_001"
}
```

引用顶层 assets 中的资源。

这样后续从本地存储切到 OSS 时，元素结构不需要变化。

------

### 4.5 root

`root` 是 Figma 页面根 Frame。

Renderer 应根据 root 创建一个 Figma Frame：

```text
name = mobile_home_demo
width = 390
height = 844
fill = #F7F8FA
```

然后递归渲染 children。

------

### 4.6 original_ref

`original_ref` 是隐藏原图参考层。

默认：

```json
"visible": false,
"opacity": 0.5
```

它用于 Figma 画布内手动对比，不用于插件内对比。

------

### 4.7 status_bar

状态栏一期直接以图片保留。

原因：

```text
状态栏可编辑价值低
不同设备差异大
识别成图层容易错
```

------

### 4.8 banner

Banner 在示例中以图片形式保留，并标记 fallback。

```json
"meta": {
  "fallback": true,
  "reason": "complex_banner_kept_as_image"
}
```

这符合 MVP 策略：

```text
复杂区域图片兜底
主要内容可编辑
```

------

### 4.9 product_card

商品卡片使用：

```text
frame + image + text + button frame
```

不使用独立 `card` type。

```json
{
  "type": "frame",
  "role": "card"
}
```

这符合 DSL v0.1 的规则：

```text
type 少
role 多
```

------

### 4.10 button

按钮使用：

```text
frame
├─ shape button_background
└─ text button_label
```

不生成真正 Figma Component。

后续组件化信息放在：

```json
"meta": {
  "componentSpec": {
    "kind": "Button"
  }
}
```

------

### 4.11 tab_bar

TabBar 使用普通 Frame 表达，不生成真正组件。

每个 TabItem 使用：

```text
frame + icon + text
```

选中状态记录在：

```json
"meta": {
  "state": "active"
}
```

Renderer 不强依赖该字段。

------

## 5. Renderer 消费顺序

Renderer 读取该 DSL 时建议顺序：

```text
1. 检查 version
2. 校验 page
3. 建立 assetId → asset 映射
4. 创建 root Frame
5. 递归渲染 root.children
6. 根据 type 创建节点
7. 应用 layout
8. 应用 style
9. 应用 content / source
10. 设置 name / visible / opacity
```

------

## 6. 渲染结果预期

该示例渲染后，Figma 中应出现：

```text
mobile_home_demo
├─ Original PNG Reference   hidden
├─ Status Bar Image
├─ Navigation Bar
│  └─ Page Title
├─ Content
│  ├─ Search Bar
│  │  ├─ Search Icon
│  │  └─ Search Placeholder
│  ├─ Banner Image
│  ├─ Section Title
│  ├─ Product Card 01
│  │  ├─ Product Image
│  │  ├─ Product Title
│  │  ├─ Product Description
│  │  ├─ Product Price
│  │  └─ Buy Button
│  └─ Product Card 02
└─ TabBar
   ├─ Tab Item - Home Active
   ├─ Tab Item - Category
   ├─ Tab Item - Cart
   ├─ Tab Item - Profile
   └─ Home Indicator
```

------

## 7. 本示例中的 MVP 取舍

该示例体现了以下 MVP 取舍：

```text
状态栏不重建，直接图片保留
Banner 复杂区域 fallback 图片
商品卡片主要内容可编辑
按钮不组件化
TabBar 不组件化
图标使用内置 SVG
图片资源通过 assetId 引用
原 PNG 参考层默认隐藏
```

这些取舍符合第一版目标：

```text
快
像
主要内容可编辑
复杂区域不拖垮系统
```

------

## 8. 后端生成建议

后端生成 DSL 时应保证：

```text
1. 所有 element.id 唯一
2. 所有 image assetId 能在 assets 中找到
3. root.type 必须为 frame
4. layout.width / height 必须大于 0
5. text 元素必须有 content.text
6. icon 元素必须有 source.kind 和 iconName
7. fallback 区域必须有 reason
8. original_ref 推荐必须存在
```

如果无法稳定生成局部结构，应优先 fallback。

------

## 9. 插件渲染建议

插件 Renderer 应保证：

```text
1. 单个元素渲染失败不导致整页崩溃
2. 图片加载失败时记录错误
3. 缺少 asset 时跳过该元素或生成占位 fallback
4. 字体加载失败时使用默认字体
5. style 字段缺失时使用默认值
6. children 为空时正常处理
```

------

## 10. 版本结论

本示例是 DSL v0.1 的参考实现样例。

它表达的是第一版 MVP 的核心思路：

```text
用简单稳定的 DSL 表达页面
用基础元素渲染 Figma
主要内容尽量可编辑
复杂内容图片兜底
不要过度组件化
不要过度建模
```

最终目标是稳定支撑：

```text
PNG → DSL → Figma 可编辑设计稿
这就是第六份文档：

**`03_DSL规范/12_DSL_v0.1_完整示例.md`**

下一份建议继续输出：

**`05_Image-to-Figma-Renderer渲染包/01_渲染包职责边界_v0.1.md`**
```