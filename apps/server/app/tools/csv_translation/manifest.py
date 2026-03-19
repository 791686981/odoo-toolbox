TOOL_MANIFEST = {
    "id": "csv-translation",
    "title": "CSV 翻译",
    "description": "上传 Odoo CSV，生成背景说明、分块翻译、人工修订并导出结果。",
    "route": "/tools/csv-translation",
    "icon": "translation",
    "category": "translation",
    "enabled": True,
    "order": 10,
    "capabilities": ["upload", "translation", "proofread", "export"],
}
