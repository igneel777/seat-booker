from uuid import UUID


class ShowNotFoundError(Exception):
    def __init__(self, show_id: UUID) -> None:
        super().__init__(f"show {show_id} not found")
        self.show_id = show_id
