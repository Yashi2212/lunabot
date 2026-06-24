from __future__ import annotations


class LunaBot:
    def __init__(self, name: str = "World") -> None:
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}! I am LunaBot." 
