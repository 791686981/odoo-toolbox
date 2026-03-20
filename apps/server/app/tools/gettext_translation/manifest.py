TOOL_MANIFEST = {
    "id": "gettext-translation",
    "title": "Gettext 翻译",
    "description": "上传 .po/.pot，按策略翻译、人工修订并导出 .po。",
    "route": "/tools/gettext-translation",
    "icon": "translation",
    "category": "translation",
    "enabled": True,
    "order": 12,
    "capabilities": ["upload", "translation", "edit", "proofread", "export"],
}
