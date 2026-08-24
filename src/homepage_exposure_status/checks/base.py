from abc import ABC, abstractmethod


class Checker(ABC):
    @abstractmethod
    async def check(self, url: str) -> bool:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
