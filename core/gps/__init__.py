from abc import ABC, abstractmethod
from ..data.models import GPSPoint

class GPSProvider(ABC):
    @abstractmethod
    def get_current_location(self) -> GPSPoint:
        pass