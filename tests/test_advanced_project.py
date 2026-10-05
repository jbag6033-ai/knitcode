from analyzer.resolver import CallResolver


def test_resolve_module_import_call():
    resolver = CallResolver("tests/fixtures/advanced_project")
    resolver.analyze_project()

    results = resolver.resolve_calls()

    assert any(
        result["caller"] == "OrderService.create_order"
        and result["callee"] == "payment.calculate_price"
        and result["target"] is not None
        and result["target"]["file"] == "payment.py"
        and result["target"]["name"] == "calculate_price"
        for result in results
    )


def test_resolve_alias_import_call():
    resolver = CallResolver("tests/fixtures/advanced_project")
    resolver.analyze_project()

    results = resolver.resolve_calls()

    assert any(
        result["caller"] == "OrderService.create_order"
        and result["callee"] == "db.save_order"
        and result["target"] is not None
        and result["target"]["file"] == "database.py"
        and result["target"]["name"] == "save_order"
        for result in results
    )


def test_resolve_self_method_call():
    resolver = CallResolver("tests/fixtures/advanced_project")
    resolver.analyze_project()

    results = resolver.resolve_calls()

    assert any(
        result["caller"] == "OrderService.create_order"
        and result["callee"] == "self.validate"
        and result["target"] is not None
        and result["target"]["name"] == "validate"
        for result in results
    )

def test_resolve_instance_method_call():
    resolver = CallResolver("tests/fixtures/advanced_project")
    resolver.analyze_project()

    results = resolver.resolve_calls()

    assert any(
        result["caller"] == "main"
        and result["callee"] == "service.create_order"
        and result["target"] is not None
        and result["target"]["file"] == "service.py"
        and result["target"]["class"] == "OrderService"
        and result["target"]["name"] == "create_order"
        for result in results
    )
    
def test_resolve_class_constructor():
    resolver = CallResolver("tests/fixtures/advanced_project")
    resolver.analyze_project()

    results = resolver.resolve_calls()

    assert any(
        result["caller"] == "main"
        and result["callee"] == "OrderService"
        and result["target"] is not None
        and result["target"]["file"] == "service.py"
        and result["target"]["name"] == "OrderService"
        and result["target"]["type"] == "class"
        for result in results
    )
    