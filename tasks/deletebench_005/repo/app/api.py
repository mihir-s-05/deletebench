from app.reports import export_formats

def available_routes() -> list[str]:
    routes = ["/reports"]
    if "csv" in export_formats():
        routes.append("/reports/export/csv")
    if "json" in export_formats():
        routes.append("/reports/export/json")
    return routes
