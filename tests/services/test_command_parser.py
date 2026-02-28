from app.services.command_parser import CommandParser, ParseStatus, ParserConfig


def test_parse_whisper_output_supports_dict_payload() -> None:
    parser = CommandParser()

    result = parser.parse_whisper_output(
        {"text": "Закрыл линию паша"},
        players=["Паша", "Лена"],
    )

    assert result.status is ParseStatus.OK
    assert result.player_name == "Паша"
    assert result.normalized_text == "закрыл линию паша"


def test_parse_whisper_output_unknown_command() -> None:
    parser = CommandParser()

    result = parser.parse_whisper_output("всем привет", players=["Паша"])

    assert result.status is ParseStatus.UNKNOWN_COMMAND
    assert result.error == "Команда не распознана"


def test_parse_whisper_output_ambiguous_name() -> None:
    parser = CommandParser(ParserConfig(confidence_threshold=50, ambiguity_delta=30))

    result = parser.parse_whisper_output(
        "Закрыл карту ан",
        players=["Анна", "Аня", "Паша"],
    )

    assert result.status is ParseStatus.AMBIGUOUS_NAME
    assert result.error is not None
    assert len(result.candidates) >= 2
