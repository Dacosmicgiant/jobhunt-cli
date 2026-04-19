from abc import ABC, abstractmethod
from jobhunt.models.job import Job
class BaseSource(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: dict) -> list[Job]:
        raise NotImplementedError