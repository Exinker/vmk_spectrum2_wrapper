from dataclasses import dataclass
from typing import TypeAlias

from vmk_spectrum2_wrapper.typing import MilliSecond


@dataclass
class DeviceEthernetConfig:
    ip: str

    change_exposure_delay: MilliSecond = 1000


DeviceConfig: TypeAlias = DeviceEthernetConfig
