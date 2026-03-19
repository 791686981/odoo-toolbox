def test_tool_registry_exposes_manifest_and_router() -> None:
    from app.tools.registry import list_tool_manifests, list_tool_routers

    manifests = list_tool_manifests()
    routers = list_tool_routers()

    assert manifests[0]["id"] == "csv-translation"
    assert any(
        route.path == "/tools/csv-translation/context-draft"
        for router in routers
        for route in router.routes
    )
