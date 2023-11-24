import sys
import time
import threading
from dataclasses import dataclass
from typing import Callable, TypeAlias

import numpy as np

from pyspectrum2 import DeviceManager, DeviceStatusCode, DeviceStatus

from .alias import Array, Second, MilliSecond, MicroSecond
from .storage import DeviceStorage


sys.path.append('cmake-build-debug/binding')


# --------        device config        --------
@dataclass
class DeviceEthernetConfig:
    ip: str

    change_exposure_delay: MilliSecond = 1000


DeviceConfig: TypeAlias = DeviceEthernetConfig


# --------        device        --------
class Device:

    def __init__(self, config: DeviceConfig, storage: DeviceStorage | None) -> None:

        self.condition = threading.Condition()

        # device
        self._device = create_device(
            config=config,
            on_frame=self._on_frame,
            on_status=self._on_status,
        )
        self._status = None
        self._change_exposure_delay = config.change_exposure_delay

        self._exposure = None
        self._storage = storage

        # connect to device
        timeout = 5
        wait_start = time.perf_counter()
        with self.condition:
            while not self.is_connected:
                if time.perf_counter() - wait_start > timeout:
                    raise ConnectionError('Connection timeout error')  # TODO: add custom exception!

                self.condition.wait(.01)

    # --------        storage        --------
    @property
    def storage(self) -> DeviceStorage | None:
        return self._storage

    def set_storage(self, storage: DeviceStorage) -> None:
        """"""
        assert isinstance(storage, DeviceStorage)

        self._storage = storage

    # --------        status        --------
    @property
    def status(self) -> DeviceStatus | None:
        return self._status

    @property
    def is_connected(self) -> bool:
        if self.status is None:
            return False

        return self.status.code in (
            DeviceStatusCode.CONNECTED,
            DeviceStatusCode.DONE_READING,  # после переподключения устройсто может находиться с состояние `DONE_READING`
        )

    @property
    def is_reading(self) -> bool:
        return self.status.code in (
            DeviceStatusCode.READING,
        )

    @property
    def is_read(self) -> bool:
        return self.status.code in (
            DeviceStatusCode.DONE_READING,
        )

    @property
    def is_ready(self) -> bool:
        return self.is_connected or self.is_read

    # --------        handlers        --------
    def await_read(self, n_frames: int | None = None) -> Array[int]:
        """Прочитать `n_frames` кадров и вернуть их (blocking)."""
        if n_frames is None:
            n_frames = self.storage.buffer_size

        assert self.is_ready, 'Device is not ready to read! Device status is {code}'.format(
            code='None' if self.status is None else self.status.code,
        )
        assert self.exposure is not None, 'Setup an exposure before reading!'

        # read
        self._device.read(n_frames)

        with self.condition:
            while not self.is_reading:
                self.condition.wait(.01)
            while not self.is_read:
                self.condition.wait(.01)

        try:
            return np.array(self.storage.data)
        finally:
            self.storage.data.clear()

    def read(self, n_frames: int | None = None) -> None:
        """Прочитать `n_frames` кадров в `storage` (non blocking)."""
        if n_frames is None:
            n_frames = self.storage.buffer_size

        assert self.is_ready, 'Device is not ready to read! Device status is {code}'.format(
            code='None' if self.status is None else self.status.code,
        )
        assert self.exposure is not None, 'Setup an exposure before reading!'
        assert self.storage is not None, 'Setup a storage before reading!'

        # read
        self._device.read(n_frames)

    # --------        callbacks        --------
    def _on_frame(self, frame: Array[int]) -> None:
        self.storage.put(frame)

    def _on_status(self, status: DeviceStatus) -> None:
        self._status = status

        # notify all
        with self.condition:
            self.condition.notify_all()

        # exception
        if status.code == DeviceStatusCode.ERROR:  # TODO: add logging
            timeout = self.storage._finished_at - self.storage._started_at
            content = '\n'.join([
                'description: {description}'.format(
                    description=status.description,
                ),
                'buffer: {size:0>4s}'.format(
                    size=len(self.storage._buffer),
                ),
                'data: {str(size):0>4s}'.format(
                    size=len(self.storage.data),
                ),
                'running for {hours}:{minutes}:{seconds}'.format(
                    hours=f'{str(int((timeout) // 3600)):0>2s}',
                    minutes=f'{str(int((timeout) // 60)):0>2s}',
                    seconds=f'{str(int((timeout) % 60)):0>2s}',
                ),
            ])

            raise ConnectionError(content)  # TODO: add custom exception!

    # --------        exposure        --------
    @property
    def exposure(self) -> MilliSecond:
        return self._exposure

    def set_exposure(self, exposure: MilliSecond) -> None:
        """Set exposure."""        
        if exposure == self._exposure:
            return

        # setup exposure
        try:
            self._device.set_exposure(self._to_microsecond(exposure))

        except AssertionError as error:
            print(error)

        else:
            self._exposure = exposure
            time.sleep(self._to_second(self._change_exposure_delay)) # delay to setup exposure

    @staticmethod
    def _to_microsecond(__exposure: MilliSecond) -> MicroSecond:
        value = int(np.round(1000 * __exposure).astype(int))

        assert value % 100 == 0, 'Invalid exposure: {value} mks!'.format(
            value=value,
        )

        return value

    @staticmethod
    def _to_second(__exposure: MilliSecond) -> Second:
        return __exposure / 1000


def create_device(config: DeviceConfig, on_frame: Callable, on_status: Callable | None) -> Device:

    if isinstance(config, DeviceEthernetConfig):
        device = DeviceManager(config.ip)
        device.set_frame_callback(on_frame)
        device.set_status_callback(on_status)
        device.run()

        return device

    raise ValueError(f'Device {type(config).__name__} is not supported yet!')
