from app.main import create_app


def test_application_metadata() -> None:
    app = create_app()

    assert app.title == "SplitBill API"
