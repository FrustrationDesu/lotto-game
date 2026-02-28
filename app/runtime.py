from __future__ import annotations

from app.repository import LottoRepository
from app.service import LottoService
from app.services.command_parser import CommandParser

repo = LottoRepository()
service = LottoService(repo)
command_parser = CommandParser()
